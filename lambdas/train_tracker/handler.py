"""
handler.py — Lambda: train-tracker
Ejecutada cada 5 minutos por EventBridge Scheduler.

Lógica:
1. Determinar qué trenes tienen ventana activa ahora mismo (ver
   schedule_matcher.py: la ventana depende del sentido y, para Madrid, del
   último retraso conocido en DynamoDB).
2. Descargar flotaLD.json de Renfe.
3. Para cada tren activo, buscar su entrada en la flota.
4. Punto de grabación en S3 según el sentido:
   - Galicia: cuando pasa por Zamora (codEstAnt == ZAMORA_CODE). Sin cierre
     de ventana por tiempo: se sigue intentando hasta capturarlo.
   - Madrid: cuando llega a Madrid Chamartín, detectado porque el tren
     desaparece de la flota (habiendo sido visto antes y a partir de
     hora_llegada_destino + retraso conocido) o porque
     codEstAnt == CHAMARTIN_CODE.
5. Si aún no ha llegado → actualizar estado en DynamoDB (se revisará
   en la próxima ejecución en 5 min).
6. Trenes Madrid cuya ventana cierra sin haber sido detectados como llegados
   se resuelven igualmente con los últimos datos conocidos
   (_resolve_expired_madrid_trains).
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3

from renfe_client import RenfeClient
from schedule_matcher import ScheduleMatcher
from datalake_writer import DatalakeWriter

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# ── Configuración desde variables de entorno ──────────────────────────────────
S3_BUCKET       = os.environ["DATALAKE_S3_BUCKET"]
DYNAMODB_TABLE  = os.environ["DYNAMODB_STATE_TABLE"]
SCHEDULES_FILE  = os.environ.get("SCHEDULES_FILE", "/var/task/train_schedules.json")
ZAMORA_CODE     = os.environ.get("ZAMORA_STATION_CODE", "30200")
CHAMARTIN_CODE  = os.environ.get("CHAMARTIN_STATION_CODE", "17000")

# ── Clientes AWS ──────────────────────────────────────────────────────────────
dynamodb = boto3.resource("dynamodb")
s3       = boto3.client("s3")

# ── Instancias de módulos ─────────────────────────────────────────────────────
renfe_client = RenfeClient()

with open(SCHEDULES_FILE, "r", encoding="utf-8") as fh:
    schedules_config = json.load(fh)

matcher = ScheduleMatcher(schedules_config)
writer  = DatalakeWriter(s3, S3_BUCKET)
state_table = dynamodb.Table(DYNAMODB_TABLE)


def lambda_handler(event, context):
    """Punto de entrada de la Lambda."""
    now_utc = datetime.now(timezone.utc)
    # Renfe opera en hora peninsular española (UTC+1 / UTC+2)
    # Usamos la hora local para comparar con los horarios de paso
    from zoneinfo import ZoneInfo
    now_local = now_utc.astimezone(ZoneInfo("Europe/Madrid"))

    logger.info("Ejecución iniciada: %s (local: %s)", now_utc.isoformat(), now_local.isoformat())

    # 1. ¿Qué trenes tienen ventana activa ahora? Para Madrid, el cierre de
    # ventana depende del último retraso conocido en DynamoDB.
    active_trains = matcher.get_active_trains(
        now_local, state_lookup=lambda cod: _get_state(cod, now_local)
    )
    logger.debug("Trenes en ventana activa: %s", [t["cod_comercial"] for t in active_trains])

    processed = 0

    if active_trains:
        # 2. Descargar flota en tiempo real
        try:
            flota = renfe_client.get_flota()
        except Exception as exc:
            logger.error("Error descargando flotaLD.json: %s", exc)
            # No hay que fallar la Lambda; se reintentará en 5 min
            return {"statusCode": 503, "error": str(exc)}

        # Indexar flota por codComercial para O(1) lookup
        flota_index = {t.get("codComercial", ""): t for t in flota}

        for scheduled_train in active_trains:
            logger.info(f'Procesando el tren {scheduled_train["cod_comercial"]} ({scheduled_train.get("sentido")})')
            cod = scheduled_train["cod_comercial"]
            # train_data puede ser None (tren no presente en la flota). Para los
            # trenes con sentido Madrid esa ausencia es significativa (llegada a
            # Chamartín), por eso lo delegamos siempre en _process_train.
            train_data = flota_index.get(cod)

            if _process_train(scheduled_train, train_data, now_local):
                processed += 1
    else:
        logger.info("No hay trenes en ventana activa.")

    # 3. Trenes Madrid cuya ventana ya cerró sin haber sido detectados como
    # llegados (ni Chamartín ni desaparición) → resolver con últimos datos
    # conocidos para no perder el dato de puntualidad de ese día.
    resolved = _resolve_expired_madrid_trains(now_local)
    processed += resolved

    logger.info(
        "Trenes procesados y grabados: %d / %d activos (%d resueltos por cierre de ventana)",
        processed, len(active_trains), resolved
    )
    return {"statusCode": 200, "active": len(active_trains), "recorded": processed}


def _process_train(scheduled: dict, live: dict | None, now_local: datetime) -> bool:
    """
    Decide si procede grabar el evento del tren.

    - Sentido Madrid: se graba cuando el tren llega a Madrid Chamartín, es decir
      cuando desaparece de la flota (habiendo sido visto antes) o cuando
      `codEstAnt == CHAMARTIN_CODE`.
    - Resto de sentidos (Galicia): se graba al pasar por Zamora
      (`codEstAnt == ZAMORA_CODE`).

    Devuelve True si se grabó un evento en S3.
    """
    cod = scheduled["cod_comercial"]

    if scheduled["sentido"] == "Madrid":
        return _process_madrid_train(scheduled, live, now_local)

    # ── Sentido Galicia: grabar al pasar por Zamora, ventana sin cierre por
    # tiempo (se sigue intentando hasta capturarlo) ──────────────────────────
    state = _get_state(cod, now_local)
    if state and state.get("done"):
        return False

    if live is None:
        logger.warning("Tren %s (%s)no encontrado en flota (¿aún no ha salido?)", cod, scheduled["sentido"])
        return False

    cod_est_ant = live.get("codEstAnt", "")
    ult_retraso = int(live.get("ultRetraso", 0) or 0)

    # ── ¿Ya pasó por Zamora? ─────────────────────────────────────────────────
    if cod_est_ant == ZAMORA_CODE:
        _record_passage(scheduled, live, now_local, capturado_en_zamora=True)

        h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
        hora_llegada_real = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=ult_retraso)
        ).strftime("%H:%M")

        _mark_done(cod, now_local, hora_llegada_real=hora_llegada_real, capturado_en_zamora=True)
        return True

    # ── Todavía no ha llegado: actualizar estado en DynamoDB ─────────────────
    _update_state(cod, scheduled, ult_retraso, cod_est_ant, now_local)
    logger.info(
        "Tren %s aún no en Zamora (última est: %s, retraso: %d min)",
        cod, cod_est_ant, ult_retraso
    )
    return False


def _process_madrid_train(scheduled: dict, live: dict | None, now_local: datetime) -> bool:
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
    if state and state.get("done"):
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
                    "pasado por Zamora → no se da por llegado", cod
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
                    cod, now_local.strftime("%H:%M"), inicio_reintentos.strftime("%H:%M")
                )
                return False

            # No hay datos en vivo; usamos el último estado conocido.
            last_known = {
                "ultRetraso": state.get("ult_retraso", 0),
                "codEstAnt":  state.get("cod_est_ant"),
            }
            _record_passage(scheduled, last_known, now_local, capturado_en_zamora=True)
            _mark_done(cod, now_local)
            logger.info(
                "Tren %s (Madrid) desaparecido de la flota tras ser visto → "
                "llegada a Chamartín registrada", cod
            )
            return True

        logger.warning(
            "Tren %s (Madrid) no encontrado en flota (¿aún no ha salido?)", cod
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
        _record_passage(scheduled, live, now_local, capturado_en_zamora=capturado_en_zamora)
        _mark_done(cod, now_local)
        logger.info("Tren %s ha llegado a Chamartín (codEstAnt=%s)", cod, cod_est_ant)
        return True

    # ── Aún en ruta hacia Madrid: actualizar estado en DynamoDB ──────────────
    # Una vez capturado pasando por Zamora, se mantiene marcado aunque el
    # tren ya haya dejado atrás esa estación en ejecuciones posteriores.
    capturado_en_zamora = bool(state and state.get("capturado_en_zamora")) or cod_est_ant == ZAMORA_CODE
    _update_state(cod, scheduled, ult_retraso, cod_est_ant, now_local, capturado_en_zamora=capturado_en_zamora)
    logger.info(
        "Tren %s (Madrid) aún en ruta (última est: %s, retraso: %d min)",
        cod, cod_est_ant, ult_retraso
    )
    return False


def _get_state(cod: str, now_local: datetime) -> dict | None:
    """Recupera el estado transitorio del tren en DynamoDB (o None si no existe)."""
    resp = state_table.get_item(
        Key={"pk": f"{cod}#{now_local.date().isoformat()}", "sk": "TRACKING"}
    )
    return resp.get("Item")


def _record_passage(scheduled: dict, live: dict, now_local: datetime, capturado_en_zamora: bool = False):
    """Construye el registro del datalake y lo escribe en S3."""
    ult_retraso = int(live.get("ultRetraso", 0) or 0)
    hora_programada = scheduled["hora_llegada_destino"]  # "HH:MM"
    h, m = map(int, hora_programada.split(":"))
    hora_real = now_local.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(minutes=ult_retraso)

    record = {
        "event_id": f"{scheduled['cod_comercial']}-{now_local.date().isoformat()}T{hora_programada}",
        "cod_comercial": scheduled["cod_comercial"],
        "sentido": scheduled["sentido"],
        "tipo_dia": scheduled["tipo_dia"],
        "dia_semana": now_local.strftime("%A"),
        "fecha_hora_evento": now_local.isoformat(),
        "hora_programada": hora_programada,
        "hora_real": hora_real.strftime("%H:%M"),
        "minutos_retraso": ult_retraso,
        "cod_est_ant": live.get("codEstAnt"),
        "cod_est_sig": live.get('codEstSig'),
        "ult_retraso_renfe": ult_retraso,
        "capturado_en_zamora": capturado_en_zamora,
    }

    writer.write(record, now_local)
    logger.info("✅ Grabado: %s retraso=%d min", record["event_id"], ult_retraso)


def _end_of_day_ttl(now_local: datetime) -> int:
    """TTL en epoch seconds correspondiente a las 23:59:59 del día local (Europe/Madrid)."""
    end_of_day = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
    return int(end_of_day.timestamp())


def _update_state(cod: str, scheduled: dict, retraso: int,
                  cod_est_ant: str, now_local: datetime, capturado_en_zamora: bool = False):
    """Persiste el estado transitorio del tren en DynamoDB."""
    ttl = _end_of_day_ttl(now_local)  # expira a las 23:59:59 del mismo día

    h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
    hora_llegada_real = (
        datetime(2000, 1, 1, h, m) + timedelta(minutes=int(retraso))
    ).strftime("%H:%M")

    state_table.put_item(Item={
        "pk":          f"{cod}#{now_local.date().isoformat()}",
        "sk":          "TRACKING",
        "cod_comercial": cod,
        "sentido":     scheduled["sentido"],
        "tipo_dia":    scheduled["tipo_dia"],
        "hora_programada": scheduled["hora_llegada_destino"],
        "hora_llegada_real": hora_llegada_real,
        "ult_retraso": retraso,
        "cod_est_ant": cod_est_ant or "UNKNOWN",
        "capturado_en_zamora": capturado_en_zamora,
        "updated_at":  now_local.isoformat(),
        "done":        False,
        "ttl":         ttl,
    })


def _mark_done(cod: str, now_local: datetime, hora_llegada_real: str | None = None,
               capturado_en_zamora: bool | None = None):
    """Marca el tren como completamente procesado para hoy."""
    # "ttl" es palabra reservada en DynamoDB → hay que usar un alias (#ttl).
    # Se fija siempre aquí, ya que este item puede no haber pasado nunca por
    # _update_state (p. ej. llegada detectada en el primer poll del tren).
    set_parts = ["done = :done", "#ttl = :ttl"]
    values = {":done": True, ":ttl": _end_of_day_ttl(now_local)}
    names = {"#ttl": "ttl"}

    if hora_llegada_real is not None:
        set_parts.append("hora_llegada_real = :hora_real")
        values[":hora_real"] = hora_llegada_real

    if capturado_en_zamora is not None:
        set_parts.append("capturado_en_zamora = :capturado")
        values[":capturado"] = capturado_en_zamora

    state_table.update_item(
        Key={"pk": f"{cod}#{now_local.date().isoformat()}", "sk": "TRACKING"},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def _resolve_expired_madrid_trains(now_local: datetime) -> int:
    """
    Recorre los trenes Madrid con estado pendiente en DynamoDB (no 'done')
    cuya ventana (hora_llegada_destino + último retraso conocido + 10 min)
    ya se ha cerrado sin haber sido detectados como llegados (ni Chamartín ni
    desaparición), y los registra igualmente con los últimos datos conocidos
    para no perder el dato de puntualidad de ese tren ese día.
    """
    resolved = 0
    for train in schedules_config["trains"]:
        if train["sentido"] != "Madrid":
            continue

        cod = train["cod_comercial"]
        state = _get_state(cod, now_local)
        if not state or state.get("done"):
            continue

        h, m = map(int, train["hora_llegada_destino"].split(":"))
        hora_llegada_programada = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
        ult_retraso_conocido = int(state.get("ult_retraso", 0) or 0)
        window_end = hora_llegada_programada + timedelta(minutes=ult_retraso_conocido + 10)

        if now_local <= window_end:
            continue  # todavía dentro de ventana, se resolverá por el flujo normal

        last_known = {
            "ultRetraso": state.get("ult_retraso", 0),
            "codEstAnt":  state.get("cod_est_ant"),
        }
        _record_passage(train, last_known, now_local, capturado_en_zamora=bool(state.get("capturado_en_zamora")))
        _mark_done(cod, now_local)
        logger.warning(
            "Tren %s (Madrid) ventana cerrada sin detección → registrado con "
            "últimos datos conocidos (retraso: %d min)", cod, ult_retraso_conocido
        )
        resolved += 1

    return resolved
