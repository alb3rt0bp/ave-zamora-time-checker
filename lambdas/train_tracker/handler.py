"""
handler.py — Lambda: train-tracker (lambda_handler) + daily-dump (daily_dump_handler)

lambda_handler se ejecuta cada 5 minutos por EventBridge Scheduler:
1. En el primer ciclo del día, siembra en DynamoDB un placeholder por cada
   tren programado hoy (_seed_todays_trains), para que el listado del día
   esté disponible desde el primer momento.
2. Determina qué trenes tienen ventana activa ahora mismo (ver
   schedule_matcher.py: la ventana depende del sentido y, para Madrid, del
   último retraso conocido en DynamoDB).
3. Descarga flotaLD.json de Renfe.
4. Para cada tren activo, busca su entrada en la flota y actualiza su estado
   en DynamoDB. Punto de "entrega" según el sentido:
   - Galicia: cuando pasa por Zamora (codEstAnt == ZAMORA_CODE). Sin cierre
     de ventana por tiempo: se sigue intentando hasta capturarlo.
   - Madrid: cuando llega a Madrid Chamartín, detectado porque el tren
     desaparece de la flota (habiendo sido visto antes y a partir de
     hora_llegada_destino + retraso conocido) o porque
     codEstAnt == CHAMARTIN_CODE.
5. Trenes Madrid cuya ventana cierra sin haber sido detectados como llegados
   se resuelven igualmente con los últimos datos conocidos
   (_resolve_expired_madrid_trains).

daily_dump_handler se ejecuta una vez al día a las 00:15 (hora de Madrid),
poco después de medianoche: vuelca a un único fichero JSONL en S3 todos los
trenes programados el día que acaba de terminar (sembrados por
_seed_todays_trains), leyendo su estado en DynamoDB (cuyo TTL no expira
hasta las 00:30, dejando margen de sobra). Los trenes que nunca se marcaron
'entregado' (nunca detectados en flotaLD.json — p. ej. cancelación por
huelga) se vuelcan igualmente, marcados con 'cancelado': true y
'minutos_retraso': null, para que consten en la observabilidad sin
contaminar medias/estadísticas de retraso (NULL se ignora en AVG() y
similares). No hay escritura a S3 durante el polling — todo el estado vive
en DynamoDB hasta el volcado diario, para minimizar el número de objetos
que Athena tiene que leer (sin capa gratuita de consultas).
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3

from renfe_client import RenfeClient
from schedule_matcher import ScheduleMatcher
from datalake_writer import DatalakeWriter

logger = logging.getLogger('handler')
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# ── Configuración desde variables de entorno ──────────────────────────────────
S3_BUCKET       = os.environ["DATALAKE_S3_BUCKET"]
DYNAMODB_TABLE  = os.environ["DYNAMODB_STATE_TABLE"]
SCHEDULES_FILE  = os.environ.get("SCHEDULES_FILE", "/var/task/train_schedules.json")
ZAMORA_CODE     = os.environ.get("ZAMORA_STATION_CODE", "30200")
CHAMARTIN_CODE  = os.environ.get("CHAMARTIN_STATION_CODE", "17000")
DELAY_ALERT_SNS_TOPIC_ARN     = os.environ.get("DELAY_ALERT_SNS_TOPIC_ARN", "")
DELAY_ALERT_THRESHOLD_MINUTES = int(os.environ.get("DELAY_ALERT_THRESHOLD_MINUTES", "15"))

# ── Clientes AWS ──────────────────────────────────────────────────────────────
dynamodb = boto3.resource("dynamodb")
s3       = boto3.client("s3")
sns      = boto3.client("sns")

with open(SCHEDULES_FILE, "r", encoding="utf-8") as fh:
    schedules_config = json.load(fh)

state_table = dynamodb.Table(DYNAMODB_TABLE)


def lambda_handler(event, context):
    """Punto de entrada de la Lambda de polling (cada 5 min)."""
    log_extra = {
        'span_id': context.aws_request_id
    }

    # ── Instancias de módulos ─────────────────────────────────────────────────────
    renfe_client = RenfeClient(log_extra)
    matcher = ScheduleMatcher(schedules_config, log_extra)

    now_utc = datetime.now(timezone.utc)
    # Renfe opera en hora peninsular española (UTC+1 / UTC+2)
    # Usamos la hora local para comparar con los horarios de paso
    from zoneinfo import ZoneInfo
    now_local = now_utc.astimezone(ZoneInfo("Europe/Madrid"))

    logger.info("Ejecución iniciada: %s (local: %s)", now_utc.isoformat(), now_local.isoformat(), extra=log_extra)

    # 0. Primer ciclo del día: sembrar en DynamoDB un placeholder por cada
    # tren programado hoy, para que el listado esté disponible desde ya.
    _seed_todays_trains(now_local, log_extra)

    # 1. ¿Qué trenes tienen ventana activa ahora? Para Madrid, el cierre de
    # ventana depende del último retraso conocido en DynamoDB.
    active_trains = matcher.get_active_trains(
        now_local, state_lookup=lambda cod: _get_state(cod, now_local)
    )
    logger.debug("Trenes en ventana activa: %s", [t["cod_comercial"] for t in active_trains], extra=log_extra)

    processed = 0

    if active_trains:
        # 2. Descargar flota en tiempo real
        try:
            flota = renfe_client.get_flota()
        except Exception as exc:
            logger.error("Error descargando flotaLD.json: %s", exc, extra=log_extra)
            # No hay que fallar la Lambda; se reintentará en 5 min
            return {"statusCode": 503, "error": str(exc)}

        # Indexar flota por codComercial para O(1) lookup
        flota_index = {t.get("codComercial", ""): t for t in flota}

        for scheduled_train in active_trains:
            logger.info(f'Procesando el tren {scheduled_train["cod_comercial"]} ({scheduled_train.get("sentido")})', extra=log_extra)
            logger.debug(f'Datos programados del tren {scheduled_train["cod_comercial"]} ({scheduled_train.get("sentido")}): {scheduled_train}', extra=log_extra)
            cod = scheduled_train["cod_comercial"]
            # train_data puede ser None (tren no presente en la flota). Para los
            # trenes con sentido Madrid esa ausencia es significativa (llegada a
            # Chamartín), por eso lo delegamos siempre en _process_train.
            train_data = flota_index.get(cod)
            logger.debug(f'Datos en tiempo real de {scheduled_train["cod_comercial"]} ({scheduled_train.get("sentido")}: {train_data}', extra=log_extra)
            if _process_train(scheduled_train, train_data, now_local, log_extra):
                processed += 1
    else:
        logger.info("No hay trenes en ventana activa.", extra=log_extra)

    # 3. Trenes Madrid cuya ventana ya cerró sin haber sido detectados como
    # llegados (ni Chamartín ni desaparición) → resolver con últimos datos
    # conocidos para no perder el dato de puntualidad de ese día.
    resolved = _resolve_expired_madrid_trains(now_local, log_extra)
    processed += resolved

    logger.info(
        "Trenes procesados y grabados: %d / %d activos (%d resueltos por cierre de ventana)",
        processed, len(active_trains), resolved,
        extra=log_extra
    )
    return {"statusCode": 200, "active": len(active_trains), "recorded": processed}


def _seed_todays_trains(now_local: datetime, log_extra: dict) -> None:
    """
    Siembra en DynamoDB un placeholder ('entregado': False, sin datos de
    Renfe todavía) para cada tren programado hoy, si no se ha hecho ya.
    Así el listado de trenes del día está disponible desde el primer ciclo,
    en vez de ir apareciendo poco a poco a medida que cada tren se procesa.

    Usa un item marcador (pk="SEED#{fecha}") para no repetir el sembrado en
    cada ciclo de 5 min; cada PutItem individual lleva además una condición
    defensiva por si dos ejecuciones se solapasen.
    """
    today = now_local.date().isoformat()
    seed_marker_pk = f"SEED#{today}"

    marker = state_table.get_item(Key={"pk": seed_marker_pk}).get("Item")
    if marker:
        return

    tipo_dia = _tipo_dia_for(now_local)
    ttl = _end_of_day_ttl(now_local)
    seeded = 0

    for train in schedules_config["trains"]:
        if train["tipo_dia"] != tipo_dia:
            continue

        try:
            state_table.put_item(
                Item={
                    "pk": f"{train['cod_comercial']}#{today}",
                    "cod_comercial": train["cod_comercial"],
                    "sentido": train["sentido"],
                    "tipo_dia": train["tipo_dia"],
                    "hora_programada": train["hora_llegada_destino"],
                    "ult_retraso": 0,
                    "capturado_en_zamora": False,
                    "entregado": False,
                    "updated_at": now_local.isoformat(),
                    "ttl": ttl,
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
            seeded += 1
        except state_table.meta.client.exceptions.ConditionalCheckFailedException:
            pass  # ya existía (p. ej. ejecuciones solapadas); no se sobrescribe

    state_table.put_item(Item={"pk": seed_marker_pk, "ttl": ttl})
    logger.info("Sembrados %d trenes de hoy (%s) en DynamoDB", seeded, tipo_dia, extra=log_extra)


def _tipo_dia_for(now_local: datetime) -> str:
    weekday = now_local.weekday()  # 0=Lunes … 6=Domingo
    if weekday in (0, 1, 2, 3, 4):
        return "laborable"
    elif weekday == 5:
        return "sabado"
    else:
        return "domingo"


def _process_train(scheduled: dict, live: dict | None, now_local: datetime, log_extra: dict) -> bool:
    """
    Decide si procede marcar el tren como entregado.

    - Sentido Madrid: se entrega cuando el tren llega a Madrid Chamartín, es decir
      cuando desaparece de la flota (habiendo sido visto antes) o cuando
      `codEstAnt == CHAMARTIN_CODE`.
    - Resto de sentidos (Galicia): se entrega al pasar por Zamora
      (`codEstAnt == ZAMORA_CODE`).

    Devuelve True si el tren se marcó como entregado en DynamoDB.
    """
    cod = scheduled["cod_comercial"]

    if scheduled["sentido"] == "Madrid":
        return _process_madrid_train(scheduled, live, now_local, log_extra)

    # ── Sentido Galicia: grabar al pasar por Zamora, ventana sin cierre por
    # tiempo (se sigue intentando hasta capturarlo) ──────────────────────────
    state = _get_state(cod, now_local)
    if state and state.get("entregado"):
        return False

    if live is None:
        logger.warning("Tren %s (%s)no encontrado en flota (¿aún no ha salido?)", cod, scheduled["sentido"], extra=log_extra)
        return False

    cod_est_ant = live.get("codEstAnt", "")
    ult_retraso = int(live.get("ultRetraso", 0) or 0)

    # ── ¿Ya pasó por Zamora? ─────────────────────────────────────────────────
    if cod_est_ant == ZAMORA_CODE:
        # Para sentido Galicia, hora_llegada_destino es el paso programado por
        # Zamora (no el destino final en Galicia, que este sistema no seguía
        # nunca): hora_llegada_corregida ES la hora de paso por Zamora.
        h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
        hora_llegada_corregida = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=ult_retraso)
        ).strftime("%H:%M")

        _mark_done(
            cod, now_local,
            hora_llegada_corregida=hora_llegada_corregida,
            hora_paso_zamora=hora_llegada_corregida,
            capturado_en_zamora=True,
            ult_retraso=ult_retraso,
        )
        _maybe_publish_delay_alert(scheduled, ult_retraso, hora_llegada_corregida, now_local, log_extra)
        logger.info("✅ Tren %s (Galicia) entregado, retraso=%d min", cod, ult_retraso, extra=log_extra)
        return True

    # ── Todavía no ha llegado: actualizar estado en DynamoDB ─────────────────
    _update_state(cod, scheduled, ult_retraso, now_local)
    logger.info(
        "Tren %s aún no en Zamora (última est: %s, retraso: %d min)",
        cod, cod_est_ant, ult_retraso,
        extra=log_extra
    )
    return False


def _process_madrid_train(scheduled: dict, live: dict | None, now_local: datetime, log_extra: dict) -> bool:
    """
    Lógica específica para trenes con sentido Madrid: el evento se graba cuando
    el tren ha llegado a Madrid Chamartín.

    Llegada detectada por cualquiera de estas dos vías:
      1. El tren ya no aparece en la flota, habiendo sido visto en una ejecución
         anterior (existe estado en DynamoDB), y ya se ha alcanzado
         hora_llegada_destino + último retraso conocido.
      2. `codEstAnt == CHAMARTIN_CODE`.

    Si la ventana se cierra sin ninguna de las dos detecciones, se resuelve
    aparte en _resolve_expired_madrid_trains().
    """
    cod   = scheduled["cod_comercial"]
    state = _get_state(cod, now_local)

    # Ya grabado en una ejecución previa → no duplicar.
    if state and state.get("entregado"):
        return False

    seen_before = state is not None

    # ── Vía 1: desaparecido de la flota tras haber sido visto → llegó a Madrid ─
    if live is None:
        if seen_before:
            # Un tren solo puede darse por llegado a Madrid si antes ha pasado
            # realmente por Zamora (evita falsos positivos de trenes marcados
            # como llegados sin haber pasado por Zamora).
            if not state.get("capturado_en_zamora", False):
                logger.warning(
                    "Tren %s (Madrid) desaparecido de la flota pero aún no había "
                    "pasado por Zamora → no se da por llegado", cod, extra=log_extra
                )
                return False

            h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
            hora_llegada_programada = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
            ult_retraso_conocido = int(state.get("ult_retraso", 0) or 0)
            inicio_reintentos = hora_llegada_programada + timedelta(minutes=ult_retraso_conocido)

            # Los reintentos (aceptar la desaparición como señal de llegada)
            # solo empiezan a partir de hora_llegada_destino + último retraso
            # conocido. Antes de eso, una desaparición se considera un hueco
            # de cobertura y simplemente se espera al siguiente ciclo; la
            # propia ventana activa (calculada en schedule_matcher, cierra
            # 10 min después de este mismo instante) limita cuántos ciclos
            # de 5 min se reintentará.
            if now_local < inicio_reintentos:
                logger.warning(
                    "Tren %s (Madrid) desaparecido de la flota pero aún no ha "
                    "llegado (hora actual: %s, hora prevista: %s)",
                    cod, now_local.strftime("%H:%M"), inicio_reintentos.strftime("%H:%M"), extra=log_extra
                )
                return False

            # No hay datos en vivo; el estado conocido ya tiene ult_retraso y
            # hora_llegada_corregida correctos de la última _update_state.
            _mark_done(cod, now_local)
            _maybe_publish_delay_alert(
                scheduled, ult_retraso_conocido, state.get("hora_llegada_corregida"), now_local, log_extra
            )
            logger.info(
                "Tren %s (Madrid) desaparecido de la flota tras ser visto → "
                "llegada a Chamartín registrada", cod, extra=log_extra
            )
            return True

        logger.warning(
            "Tren %s (Madrid) no encontrado en flota (¿aún no ha salido?)", cod, extra=log_extra
        )
        return False

    cod_est_ant = live.get("codEstAnt", "")
    ult_retraso = int(live.get("ultRetraso", 0) or 0)

    # ── Vía 2: última estación == Chamartín → llegó a Madrid ─────────────────
    if cod_est_ant == CHAMARTIN_CODE:
        # No hay guardia previa de capturado_en_zamora en esta vía: se refleja
        # el valor conocido tal cual, para poder auditar en Athena los casos
        # en los que un tren llega a Chamartín sin haber pasado por Zamora.
        capturado_en_zamora = bool(state and state.get("capturado_en_zamora"))

        h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
        hora_llegada_corregida = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=ult_retraso)
        ).strftime("%H:%M")

        _mark_done(
            cod, now_local,
            hora_llegada_corregida=hora_llegada_corregida,
            capturado_en_zamora=capturado_en_zamora,
            ult_retraso=ult_retraso,
        )
        _maybe_publish_delay_alert(scheduled, ult_retraso, hora_llegada_corregida, now_local, log_extra)
        logger.info("Tren %s ha llegado a Chamartín (codEstAnt=%s)", cod, cod_est_ant, extra=log_extra)
        return True

    # ── Aún en ruta hacia Madrid: actualizar estado en DynamoDB ──────────────
    # Una vez capturado pasando por Zamora, se mantiene marcado aunque el
    # tren ya haya dejado atrás esa estación en ejecuciones posteriores.
    capturado_en_zamora_previo = bool(state and state.get("capturado_en_zamora"))
    capturado_en_zamora = capturado_en_zamora_previo or cod_est_ant == ZAMORA_CODE

    if capturado_en_zamora_previo:
        # Ya se fijó en un ciclo anterior: se conserva tal cual (put_item
        # reemplaza el item entero, así que hay que reenviarlo cada vez).
        hora_paso_zamora = state.get("hora_paso_zamora")
    elif cod_est_ant == ZAMORA_CODE:
        # Primera vez que se detecta el paso por Zamora: para sentido Madrid,
        # hora_salida es el paso programado por Zamora (el origen real del
        # tren, en Galicia, no se sigue en esta app).
        h, m = map(int, scheduled["hora_salida"].split(":"))
        hora_paso_zamora = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=ult_retraso)
        ).strftime("%H:%M")
    else:
        hora_paso_zamora = None

    _update_state(
        cod, scheduled, ult_retraso, now_local,
        capturado_en_zamora=capturado_en_zamora,
        hora_paso_zamora=hora_paso_zamora,
    )
    logger.info(
        "Tren %s (Madrid) aún en ruta (última est: %s, retraso: %d min)",
        cod, cod_est_ant, ult_retraso, extra=log_extra
    )
    return False


def _get_state(cod: str, now_local: datetime) -> dict | None:
    """Recupera el estado transitorio del tren en DynamoDB (o None si no existe)."""
    resp = state_table.get_item(
        Key={"pk": f"{cod}#{now_local.date().isoformat()}"}
    )
    return resp.get("Item")


def _end_of_day_ttl(now_local: datetime) -> int:
    """
    TTL en epoch seconds: 00:30 del día siguiente (hora local). Se deja un
    margen tras la medianoche (en vez de expirar justo a las 23:59:59) para
    que daily_dump_handler pueda leer los datos del día con seguridad antes
    de que el barrido de TTL de DynamoDB (best-effort, no instantáneo) los
    elimine — el último ciclo de polling llega hasta las 23:59.
    """
    next_day = now_local.date() + timedelta(days=1)
    cutoff = now_local.replace(
        year=next_day.year, month=next_day.month, day=next_day.day,
        hour=0, minute=30, second=0, microsecond=0,
    )
    return int(cutoff.timestamp())


def _update_state(cod: str, scheduled: dict, retraso: int,
                  now_local: datetime, capturado_en_zamora: bool = False,
                  hora_paso_zamora: str | None = None):
    """Persiste el estado transitorio del tren en DynamoDB."""
    ttl = _end_of_day_ttl(now_local)  # expira a las 23:59:59 del mismo día

    h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
    hora_llegada_corregida = (
        datetime(2000, 1, 1, h, m) + timedelta(minutes=int(retraso))
    ).strftime("%H:%M")

    item = {
        "pk":          f"{cod}#{now_local.date().isoformat()}",
        "cod_comercial": cod,
        "sentido":     scheduled["sentido"],
        "tipo_dia":    scheduled["tipo_dia"],
        "hora_programada": scheduled["hora_llegada_destino"],
        "hora_llegada_corregida": hora_llegada_corregida,
        "ult_retraso": retraso,
        "capturado_en_zamora": capturado_en_zamora,
        "updated_at":  now_local.isoformat(),
        "entregado":   False,
        "ttl":         ttl,
    }
    # put_item reemplaza el item entero: si no se pasa (p. ej. aún no
    # capturado), se omite el atributo en vez de fabricar un valor.
    if hora_paso_zamora is not None:
        item["hora_paso_zamora"] = hora_paso_zamora

    state_table.put_item(Item=item)


def _mark_done(cod: str, now_local: datetime, hora_llegada_corregida: str | None = None,
               capturado_en_zamora: bool | None = None, ult_retraso: int | None = None,
               hora_paso_zamora: str | None = None):
    """Marca el tren como entregado (procesado) para hoy."""
    # "ttl" es palabra reservada en DynamoDB → hay que usar un alias (#ttl).
    # Se fija siempre aquí, ya que este item puede no haber pasado nunca por
    # _update_state (p. ej. llegada detectada en el primer poll del tren).
    set_parts = ["entregado = :entregado", "#ttl = :ttl"]
    values = {":entregado": True, ":ttl": _end_of_day_ttl(now_local)}
    names = {"#ttl": "ttl"}

    if hora_llegada_corregida is not None:
        set_parts.append("hora_llegada_corregida = :hora_corregida")
        values[":hora_corregida"] = hora_llegada_corregida

    if capturado_en_zamora is not None:
        set_parts.append("capturado_en_zamora = :capturado")
        values[":capturado"] = capturado_en_zamora

    if ult_retraso is not None:
        # Debe ir siempre junto a hora_llegada_corregida: si no, el campo
        # ult_retraso del item queda desfasado respecto al retraso realmente
        # usado para calcularla (el de la última vez que se llamó a
        # _update_state, no el del ciclo en que se captura la llegada).
        set_parts.append("ult_retraso = :ult_retraso")
        values[":ult_retraso"] = ult_retraso

    if hora_paso_zamora is not None:
        set_parts.append("hora_paso_zamora = :hora_paso_zamora")
        values[":hora_paso_zamora"] = hora_paso_zamora

    state_table.update_item(
        Key={"pk": f"{cod}#{now_local.date().isoformat()}"},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def _maybe_publish_delay_alert(scheduled: dict, ult_retraso: int,
                                hora_llegada_corregida: str | None,
                                now_local: datetime, log_extra: dict) -> None:
    """
    Publica un evento en SNS cuando un tren se acaba de marcar entregado con
    más de DELAY_ALERT_THRESHOLD_MINUTES minutos de retraso, para que
    tweet_notifier lo recoja y publique el tuit correspondiente. Desacoplado
    vía SNS para que un fallo/lentitud de la API de X no afecte al ciclo de
    polling. Un fallo al publicar se loguea pero no debe tirar la Lambda: el
    tren ya ha quedado grabado como entregado antes de esta llamada.
    """
    if ult_retraso <= DELAY_ALERT_THRESHOLD_MINUTES:
        return

    try:
        sns.publish(
            TopicArn=DELAY_ALERT_SNS_TOPIC_ARN,
            Message=json.dumps({
                "cod_comercial": scheduled["cod_comercial"],
                "sentido": scheduled["sentido"],
                "hora_programada": scheduled["hora_llegada_destino"],
                "hora_llegada_corregida": hora_llegada_corregida,
                "minutos_retraso": ult_retraso,
                "fecha": now_local.date().isoformat(),
            }),
        )
        logger.info(
            "Alerta de retraso publicada en SNS para %s (retraso=%d min)",
            scheduled["cod_comercial"], ult_retraso, extra=log_extra
        )
    except Exception as exc:
        logger.error(
            "Error publicando alerta de retraso en SNS para %s: %s",
            scheduled["cod_comercial"], exc, extra=log_extra
        )


def _resolve_expired_madrid_trains(now_local: datetime, log_extra: dict) -> int:
    """
    Recorre los trenes Madrid con estado pendiente en DynamoDB (no 'entregado')
    cuya ventana (hora_llegada_destino + último retraso conocido + 10 min)
    ya se ha cerrado sin haber sido detectados como llegados (ni Chamartín ni
    desaparición), y los marca igualmente como entregados con los últimos
    datos conocidos para no perder el dato de puntualidad de ese tren ese día.

    Excepción: si el tren nunca se llegó a ver en flotaLD.json en todo el día
    (capturado_en_zamora sigue en False, tal y como lo deja el placeholder de
    _seed_todays_trains), no se fuerza la entrega. Forzarla dejaría un
    registro con ult_retraso=0 como si el tren hubiese circulado puntual,
    cuando en realidad no hay ninguna evidencia de que haya circulado (p. ej.
    cancelación por huelga) — contaminaría el Data Lake con falsos positivos.
    Se deja el item con entregado=False: el filtro de daily_dump_handler ya lo
    excluye del volcado, y el TTL lo limpia solo.
    """
    resolved = 0
    for train in schedules_config["trains"]:
        if train["sentido"] != "Madrid":
            continue

        cod = train["cod_comercial"]
        state = _get_state(cod, now_local)
        if not state or state.get("entregado"):
            continue

        h, m = map(int, train["hora_llegada_destino"].split(":"))
        hora_llegada_programada = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
        ult_retraso_conocido = int(state.get("ult_retraso", 0) or 0)
        window_end = hora_llegada_programada + timedelta(minutes=ult_retraso_conocido + 10)

        if now_local <= window_end:
            continue  # todavía dentro de ventana, se resolverá por el flujo normal

        if not state.get("capturado_en_zamora", False):
            logger.warning(
                "Tren %s (Madrid) ventana cerrada sin haberse visto nunca en flotaLD.json "
                "(¿cancelación/huelga?) → no se marca como entregado", cod, extra=log_extra
            )
            continue

        # El estado ya tiene ult_retraso y hora_llegada_corregida correctos
        # de la última _update_state; basta con marcarlo como entregado.
        _mark_done(cod, now_local)
        logger.warning(
            "Tren %s (Madrid) ventana cerrada sin detección → entregado con "
            "últimos datos conocidos (retraso: %d min)", cod, ult_retraso_conocido, extra=log_extra
        )
        resolved += 1

    return resolved


def daily_dump_handler(event, context):
    """
    Lambda de volcado diario. Se ejecuta poco después de medianoche (hora de
    Madrid), tras el último ciclo de polling del día anterior y antes de que
    el TTL de DynamoDB (00:30) pueda barrer sus datos. Lee de DynamoDB todos
    los trenes programados el día que acaba de terminar (sembrados por
    _seed_todays_trains, que crea un item por cada uno) y los escribe en un
    único fichero JSONL en S3.

    Un tren que nunca llegó a marcarse 'entregado' (nunca detectado en
    flotaLD.json en todo el día) se vuelca igualmente como 'cancelado': true,
    con 'minutos_retraso'/'hora_llegada_corregida' a null — no hay dato real
    de retraso que reportar, y forzar un valor (p. ej. 0) contaminaría medias
    y estadísticas como si el tren hubiese circulado puntual.
    """
    log_extra = {'span_id': context.aws_request_id}

    now_utc = datetime.now(timezone.utc)
    from zoneinfo import ZoneInfo
    now_local = now_utc.astimezone(ZoneInfo("Europe/Madrid"))
    target_date = now_local.date() - timedelta(days=1)
    target_date_iso = target_date.isoformat()

    logger.info("Volcado diario iniciado para %s", target_date_iso, extra=log_extra)

    records = []
    scan_kwargs = {"FilterExpression": "attribute_exists(cod_comercial)"}
    while True:
        resp = state_table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            if not item["pk"].endswith(f"#{target_date_iso}"):
                continue  # de otro día

            entregado = bool(item.get("entregado"))
            records.append({
                "event_id": f"{item['cod_comercial']}-{target_date_iso}T{item['hora_programada']}",
                "cod_comercial": item["cod_comercial"],
                "sentido": item["sentido"],
                "tipo_dia": item["tipo_dia"],
                "dia_semana": target_date.strftime("%A"),
                "hora_programada": item["hora_programada"],
                "hora_llegada_corregida": item.get("hora_llegada_corregida") if entregado else None,
                "hora_paso_zamora": item.get("hora_paso_zamora") if entregado else None,
                "minutos_retraso": int(item.get("ult_retraso", 0)) if entregado else None,
                "cancelado": not entregado,
            })
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    if not records:
        logger.info("Ningún tren programado el %s; no se escribe fichero.", target_date_iso, extra=log_extra)
        return {"statusCode": 200, "written": 0}

    writer = DatalakeWriter(s3, S3_BUCKET, log_extra)
    key = writer.write_daily_batch(records, target_date)

    logger.info("Volcado diario completado: %d trenes en %s", len(records), key, extra=log_extra)
    return {"statusCode": 200, "written": len(records), "key": key}
