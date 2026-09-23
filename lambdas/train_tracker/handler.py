"""
handler.py — Lambda: train-tracker (lambda_handler) + daily-dump (daily_dump_handler)

lambda_handler se ejecuta cada 5 minutos por EventBridge Scheduler:
0. Resuelve el horario de trenes de HOY (ver schedule_resolver.py): caché en
   S3 (schedules/{fecha}.json) → si no existe, descarga y parsea el GTFS
   estático de Renfe y la cachea → si todo eso falla, cae al fichero
   estático embebido (train_schedules.json) y avisa por email. Solo el
   primer ciclo del día que no encuentre ya la caché en S3 llega a
   descargar/parsear GTFS; el resto del día lee la caché.
1. En el primer ciclo del día, siembra en DynamoDB un placeholder por cada
   tren de ese horario (_seed_todays_trains), para que el listado del día
   esté disponible desde el primer momento. Solo en el tramo diurno: un día
   nunca se siembra fuera de su propio día calendario.
2. Determina qué trenes tienen ventana activa ahora mismo (ver
   schedule_matcher.py: la ventana depende del sentido y, para Madrid, del
   último retraso conocido en DynamoDB) sobre ese mismo horario del día.
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

El polling "normal" (pasos 0-5) para a las 23:59 (EventBridge Scheduler, ver
infrastructure/template.yaml), pero un tren muy retrasado puede seguir en
ruta después de esa hora. Por eso hay un tramo extra de polling de madrugada
[00:00, NIGHT_TAIL_WINDOW_MINUTES) — 30 min por defecto — que sigue
perteneciendo operativamente al día que acaba de terminar (ver
_operational_date): en ese tramo no se recalculan ventanas de apertura
(_get_pending_trains sustituye a ScheduleMatcher.get_active_trains), solo se
sigue intentando cualquier tren de ese día aún no marcado 'entregado'.
_schedule_datetime ancla las horas programadas al día OPERATIVO (no al día
calendario de "ahora"), para que las comparaciones de cierre de ventana
sigan siendo correctas cruzando medianoche. En ese tramo NO se siembra (ver
_seed_todays_trains): el día ya se sembró por la mañana y resembrarlo
borraría el día tal y como ocurrió el 2026-09-18.

daily_dump_handler se ejecuta una vez al día a la 01:00 (hora de Madrid),
después de que termine el tramo de madrugada: vuelca a un único fichero
JSONL en S3 todos los trenes programados el día que acaba de terminar
(sembrados por _seed_todays_trains), leyendo su estado en DynamoDB (cuyo TTL
deja un día entero de margen tras el volcado — ver _end_of_day_ttl). Si el
marcador SEED# del día falta o es de otro día, el estado no es fiable y el
volcado se aborta con aviso (_check_seed_marker). Los trenes que nunca se
marcaron 'entregado' (nunca detectados en flotaLD.json en todo el día,
madrugada incluida — p. ej. cancelación por huelga) se vuelcan igualmente,
marcados con 'cancelado': true y 'minutos_retraso': null, para que consten
en la observabilidad sin contaminar medias/estadísticas de retraso (NULL se
ignora en AVG() y similares). El estado de cada tren vive en DynamoDB hasta
el volcado diario, para minimizar el número de objetos que Athena tiene que
leer (sin capa gratuita de consultas) — la única escritura a S3 durante el
polling es la caché del horario del día (schedules/{fecha}.json, una vez al
día).
"""

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import boto3

from renfe_client import RenfeClient
from schedule_matcher import ScheduleMatcher
from datalake_writer import DatalakeWriter
from metrics_writer import MetricsWriter
from gtfsrt_client import GtfsRtClient
from gtfsrt_matcher import find_stop_time_update
from schedule_resolver import resolve_todays_schedule

logger = logging.getLogger("train_tracker")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# ── Configuración desde variables de entorno ──────────────────────────────────
S3_BUCKET       = os.environ["DATALAKE_S3_BUCKET"]
DYNAMODB_TABLE  = os.environ["DYNAMODB_STATE_TABLE"]
DYNAMODB_METRICS_TABLE = os.environ["DYNAMODB_METRICS_TABLE"]
SCHEDULES_FILE  = os.environ.get("SCHEDULES_FILE", "/var/task/train_schedules.json")
ZAMORA_CODE     = os.environ.get("ZAMORA_STATION_CODE", "30200")
CHAMARTIN_CODE  = os.environ.get("CHAMARTIN_STATION_CODE", "17000")
GTFS_RT_ENRICHMENT_ENABLED = os.environ.get("GTFS_RT_ENRICHMENT_ENABLED", "true").lower() == "true"
DELAY_ALERT_SNS_TOPIC_ARN     = os.environ.get("DELAY_ALERT_SNS_TOPIC_ARN", "")
DELAY_ALERT_THRESHOLD_MINUTES = int(os.environ.get("DELAY_ALERT_THRESHOLD_MINUTES", "15"))
FLAGSHIP_MADRID_TRAIN_CODE    = os.environ.get("FLAGSHIP_MADRID_TRAIN_CODE", "04154")
# Umbral de "retraso significativo" para las métricas precalculadas
# (TRAIN#/WEEK#/MONTH# en DYNAMODB_METRICS_TABLE). Deliberadamente
# independiente de DELAY_ALERT_THRESHOLD_MINUTES (ese controla los tuits
# automáticos): ambos comparten hoy el mismo valor por defecto por
# coincidencia, no porque sean el mismo concern.
SIGNIFICANT_DELAY_THRESHOLD_MINUTES = int(os.environ.get("SIGNIFICANT_DELAY_THRESHOLD_MINUTES", "15"))
# Renfe ha reportado alguna vez un ultRetraso disparatado (p. ej. -562 min):
# un bug puntual de su servicio, no un tren circulando con adelanto real.
DATA_QUALITY_ALERT_SNS_TOPIC_ARN = os.environ.get("DATA_QUALITY_ALERT_SNS_TOPIC_ARN", "")
NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES = int(
    os.environ.get("NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES", "-10")
)
# El polling normal para en 23:59 (ver EventBridge Scheduler en
# infrastructure/template.yaml). Un tren muy retrasado puede seguir en ruta
# después de esa hora (motivo: un tren llegó a las 23:26 y casi se sale de
# margen), así que se añade un tramo extra de polling de madrugada
# [00:00, NIGHT_TAIL_WINDOW_MINUTES) que sigue perteneciendo operativamente
# al día que acaba de terminar (ver _operational_date) — debe coincidir con
# la regla "ScheduleNightTail" del template, y el volcado diario corre 30 min
# después de que termine (01:00 con el valor por defecto). En minutos, no en
# horas, porque el tramo ya no dura horas completas.
NIGHT_TAIL_WINDOW_MINUTES = int(os.environ.get("NIGHT_TAIL_WINDOW_MINUTES", "30"))
# Hora local ("HH:MM") a la que expira el estado del día en DynamoDB, y días
# COMPLETOS de margen que se le suman (ver _end_of_day_ttl). Con los valores
# por defecto el estado del día D vive hasta la 01:30 de D+2, ~24 h después
# del volcado diario. Deliberadamente NO va pegado al volcado: cuando el TTL
# expiraba 15 min después (02:30 frente a un volcado a las 02:15), el
# despliegue del 2026-09-18 cambió la fórmula a media tarde, los items del
# día (y su marcador SEED#) escritos con la fórmula anterior expiraron ANTES
# del volcado, y el tramo de madrugada los volvió a sembrar como
# placeholders → el Data Lake registró el día entero como cancelado. Un día
# entero de margen absorbe además un volcado que falle y se reintente al día
# siguiente. Coste despreciable: ~300 items/día en una tabla on-demand.
STATE_TTL_CUTOFF_HHMM = os.environ.get("STATE_TTL_CUTOFF_HHMM", "01:30")
STATE_TTL_MARGIN_DAYS = int(os.environ.get("STATE_TTL_MARGIN_DAYS", "1"))
# Proporción de trenes marcados 'cancelado' en el volcado diario a partir de
# la cual se avisa por email: una jornada de huelga real puede serlo, pero lo
# normal es que un porcentaje alto sea síntoma de que el polling no funcionó.
MAX_CANCELLED_RATIO_ALERT = float(os.environ.get("MAX_CANCELLED_RATIO_ALERT", "0.5"))

# ── Clientes AWS ──────────────────────────────────────────────────────────────
dynamodb = boto3.resource("dynamodb")
s3       = boto3.client("s3")
sns      = boto3.client("sns")


# Fallback estático (todos los tipo_dia mezclados) para cuando la resolución
# desde GTFS falla o está desactivada — ver schedule_resolver.py, que filtra
# esto a los trenes de hoy antes de dárselo a ScheduleMatcher.
with open(SCHEDULES_FILE, "r", encoding="utf-8") as fh:
    static_schedule_fallback = json.load(fh)

state_table = dynamodb.Table(DYNAMODB_TABLE)
metrics_table = dynamodb.Table(DYNAMODB_METRICS_TABLE)


def _operational_date(now_local: datetime) -> date:
    """
    El día OPERATIVO de un ciclo de polling: coincide con el día calendario
    salvo en el tramo de madrugada [00:00, NIGHT_TAIL_WINDOW_MINUTES) hora de
    Madrid, que sigue perteneciendo al día que acaba de terminar — ese tramo
    de polling extra existe precisamente para seguir comprobando trenes
    todavía en ruta cuando el último ciclo "normal" (23:59) los dejó sin
    resolver. Todo el estado en DynamoDB (pk, TTL) se indexa por este día
    operativo, no por now_local.date().
    """
    if now_local.hour * 60 + now_local.minute < NIGHT_TAIL_WINDOW_MINUTES:
        return now_local.date() - timedelta(days=1)
    return now_local.date()


def _schedule_datetime(today: date, hhmm: str, tzinfo, offset_dias: int = 0) -> datetime:
    """
    Construye un datetime absoluto para "HH:MM" anclado en `today` (el día
    OPERATIVO — ver _operational_date), no en now_local.date(). Reemplaza los
    usos de now_local.replace(hour=..., minute=...): durante el tramo de
    madrugada, now_local ya está en el día calendario siguiente, así que
    anclar ahí daría una hora programada equivocada (un día adelantada) y
    rompería las comparaciones de cierre de ventana.

    `offset_dias` son los días que esa hora de reloj va por delante del día
    operativo (ver gtfs_schedule_builder._day_offset): 1 para la llegada de
    un tren que sale a las 23:50 y llega pasada la medianoche, cuya hora
    programada pertenece al día siguiente aunque el tren sea "de ayer".
    """
    h, m = map(int, hhmm.split(":"))
    return datetime(today.year, today.month, today.day, h, m, tzinfo=tzinfo) + timedelta(days=offset_dias)


def _get_pending_trains(today: date, trains_today: list[dict], log_extra: dict) -> list[dict]:
    """
    trains_today que todavía no están marcados 'entregado' en DynamoDB para
    `today`. Se usa en el tramo de madrugada en vez de
    ScheduleMatcher.get_active_trains: ese cálculo de ventana está pensado
    para el horario normal (now_local y las horas programadas en el mismo
    día calendario) y no para "sigue abierto desde ayer" — aquí basta con
    seguir intentando cualquier tren que aún no se haya resuelto, sin
    recalcular ventanas de apertura que ya no aplican a estas horas.
    """
    pending = []
    for train in trains_today:
        state = _get_state(train["cod_comercial"], today)
        if state and state.get("entregado"):
            continue
        pending.append(train)
    return pending


def lambda_handler(event, context):
    """Punto de entrada de la Lambda de polling (cada 5 min)."""
    log_extra = {
        'span_id': context.aws_request_id
    }

    # ── Instancias de módulos ─────────────────────────────────────────────────────
    renfe_client = RenfeClient(log_extra)

    now_utc = datetime.now(timezone.utc)
    # Renfe opera en hora peninsular española (UTC+1 / UTC+2)
    # Usamos la hora local para comparar con los horarios de paso
    now_local = now_utc.astimezone(ZoneInfo("Europe/Madrid"))
    today = _operational_date(now_local)
    night_tail = today != now_local.date()

    logger.info(
        "Ejecución iniciada: %s (local: %s, día operativo: %s%s)",
        now_utc.isoformat(), now_local.isoformat(), today.isoformat(),
        " — tramo de madrugada" if night_tail else "",
        extra=log_extra,
    )

    # 0. Horario del día operativo: caché en S3 → GTFS (y cachear) → fallback
    # estático. Tanto el sembrado como las ventanas de polling se calculan
    # sobre este mismo resultado (ver schedule_resolver.py). En el tramo de
    # madrugada esto relee la caché ya escrita durante el día que termina
    # (today = ayer), nunca vuelve a descargar GTFS para "hoy".
    todays_schedule = resolve_todays_schedule(
        s3, S3_BUCKET, today, ZAMORA_CODE, CHAMARTIN_CODE,
        static_schedule_fallback,
        lambda msg: _publish_schedule_fallback_alert(msg, log_extra),
        log_extra,
    )
    trains_today = todays_schedule["trains"]
    matcher = ScheduleMatcher(todays_schedule, log_extra)

    if night_tail:
        # Tramo de madrugada: NO se siembra. El día operativo es el que acaba
        # de terminar y se sembró hace ~17 h; si su marcador SEED# no
        # estuviera, sembrar aquí no recupera nada, sino que reescribe el día
        # entero como placeholders sin entregar — justo lo que ocurrió el
        # 2026-09-18, cuando el TTL antiguo barrió el día a mitad del tramo
        # de madrugada y el volcado encontró trenes recién resembrados y los
        # dio todos por cancelados.
        #
        # Tampoco se recalculan ventanas de apertura (ya no aplican a estas
        # horas): se sigue intentando cualquier tren de ayer sin resolver.
        active_trains = _get_pending_trains(today, trains_today, log_extra)
        logger.debug(
            "Tramo de madrugada: %d trenes de %s aún pendientes",
            len(active_trains), today.isoformat(), extra=log_extra,
        )
    else:
        # Primer ciclo del día operativo: sembrar en DynamoDB un placeholder
        # por cada tren programado, para que el listado esté disponible desde
        # ya. Idempotente vía el marcador SEED#{today}.
        _seed_todays_trains(today, now_local, trains_today, log_extra)

        # 1. ¿Qué trenes tienen ventana activa ahora? Para Madrid, el cierre
        # de ventana depende del último retraso conocido en DynamoDB.
        active_trains = matcher.get_active_trains(
            now_local, state_lookup=lambda cod: _get_state(cod, today)
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
            if train_data is not None:
                logger.info(
                    "Tren %s detectado en flota: %s,%s (pegar en Google Maps), codEstAnt=%s",
                    cod, train_data.get("latitud"), train_data.get("longitud"), train_data.get("codEstAnt"),
                    extra=log_extra,
                )
            if _process_train(scheduled_train, train_data, today, now_local, log_extra):
                processed += 1
    else:
        logger.info("No hay trenes en ventana activa.", extra=log_extra)

    # 3. Trenes Madrid cuya ventana ya cerró sin haber sido detectados como
    # llegados (ni Chamartín ni desaparición) → resolver con últimos datos
    # conocidos para no perder el dato de puntualidad de ese día.
    resolved = _resolve_expired_madrid_trains(today, now_local, trains_today, log_extra)
    processed += resolved

    logger.info(
        "Trenes procesados y grabados: %d / %d activos (%d resueltos por cierre de ventana)",
        processed, len(active_trains), resolved,
        extra=log_extra
    )
    return {"statusCode": 200, "active": len(active_trains), "recorded": processed}


def _seed_todays_trains(today: date, now_local: datetime, trains_today: list[dict], log_extra: dict) -> None:
    """
    Siembra en DynamoDB un placeholder ('entregado': False, sin datos de
    Renfe todavía) para cada tren de trains_today (ya resuelto para `today`
    por schedule_resolver.py — GTFS o fallback estático), si no se ha hecho
    ya. Así el listado de trenes del día está disponible desde el primer
    ciclo, en vez de ir apareciendo poco a poco a medida que cada tren se
    procesa.

    Usa un item marcador (pk="SEED#{fecha}", con la marca de tiempo del
    sembrado en 'seeded_at') para no repetir el sembrado en cada ciclo de 5
    min; cada PutItem individual lleva además una condición defensiva por si
    dos ejecuciones se solapasen.

    La ausencia del marcador NO se interpreta como "hay que sembrar" sin más:
    un día solo puede sembrarse durante su propio día calendario. Si el
    marcador falta fuera de ese día (p. ej. porque el TTL ya barrió el día
    entero, como el 2026-09-18), sembrar no recupera nada — rellenaría el día
    de placeholders sin entregar que el volcado diario leería como
    cancelaciones. En ese caso se avisa y no se toca nada.
    """
    today_iso = today.isoformat()
    seed_marker_pk = f"SEED#{today_iso}"

    marker = state_table.get_item(Key={"pk": seed_marker_pk}).get("Item")
    if marker:
        return

    if now_local.date() != today:
        # Tramo de madrugada (o cualquier otro ciclo cuyo día operativo ya no
        # es el día calendario): el día ya se sembró hace horas; si el
        # marcador no está, es que el estado del día se ha perdido.
        message = (
            f"No se ha sembrado el día {today_iso}: falta su marcador SEED# pero la "
            f"hora local actual ({now_local.isoformat()}) ya no pertenece a ese día "
            f"calendario. El estado del día puede haber expirado antes de tiempo "
            f"(revisar TTL); el volcado diario se abortará para no registrar el día "
            f"entero como cancelado."
        )
        logger.error(message, extra=log_extra)
        _publish_alert("[Zamora Trains] Sembrado fuera de día bloqueado", message, log_extra)
        return

    ttl = _end_of_day_ttl(today)
    seeded = 0
    preexisting: list[str] = []

    for train in trains_today:
        try:
            state_table.put_item(
                Item={
                    "pk": f"{train['cod_comercial']}#{today_iso}",
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
            # Ya existía; no se sobrescribe nunca (ver _alert_if_day_had_progress).
            preexisting.append(train["cod_comercial"])

    state_table.put_item(
        Item={"pk": seed_marker_pk, "seeded_at": now_local.isoformat(), "ttl": ttl}
    )
    logger.info("Sembrados %d trenes de hoy (%s) en DynamoDB", seeded, today_iso, extra=log_extra)

    if preexisting:
        _alert_if_day_had_progress(today, preexisting, log_extra)


def _alert_if_day_had_progress(today: date, preexisting: list[str], log_extra: dict) -> None:
    """
    Se llama cuando el sembrado ha encontrado items que ya existían pese a no
    haber marcador. Dos ejecuciones solapadas del primer ciclo del día lo
    explican sin más (los items del otro sembrado son placeholders idénticos)
    y no merecen aviso. Si en cambio alguno de esos items ya tenía progreso
    real (entregado, retraso conocido u hora corregida), el marcador ha
    desaparecido con el día a medias: nada se ha sobrescrito (el PutItem es
    condicional), pero conviene revisarlo porque apunta a un TTL demasiado
    corto.
    """
    con_progreso = []
    for cod in preexisting:
        state = _get_state(cod, today) or {}
        if (state.get("entregado") or int(state.get("ult_retraso", 0) or 0) != 0
                or state.get("hora_llegada_corregida")):
            con_progreso.append(cod)

    if not con_progreso:
        logger.info(
            "Sembrado: %d trenes ya existían como placeholder (ejecuciones solapadas)",
            len(preexisting), extra=log_extra,
        )
        return

    message = (
        f"El sembrado del día {today.isoformat()} no ha encontrado su marcador SEED# "
        f"pero {len(con_progreso)} trenes ya tenían estado real en DynamoDB "
        f"({', '.join(sorted(con_progreso))}). No se ha sobrescrito ninguno, pero el "
        f"marcador no debería desaparecer antes que los trenes del día: revisar el TTL."
    )
    logger.error(message, extra=log_extra)
    _publish_alert("[Zamora Trains] Marcador de sembrado ausente con el día a medias", message, log_extra)


def _fetch_gtfsrt_entities(log_extra: dict) -> list[dict]:
    """
    Descarga trip_updates_LD.json de forma segura para el enriquecimiento
    aditivo (ver gtfsrt_client.py / CLAUDE.md): cualquier fallo se registra y
    se ignora devolviendo una lista vacía, nunca bloquea el flujo de captura
    probado basado en flotaLD.json.
    """
    if not GTFS_RT_ENRICHMENT_ENABLED:
        return []
    try:
        return GtfsRtClient(log_extra, timeout_seconds=10).get_trip_updates()
    except Exception as exc:
        logger.warning("No se pudo descargar trip_updates_LD.json: %s", exc, extra=log_extra)
        return []


def _enrich_with_gtfsrt(cod: str, sentido: str, endpoint_station_code: str, log_extra: dict) -> dict:
    """
    Enriquecimiento aditivo y best-effort a partir del feed GTFS-RT oficial
    de Renfe: añade minutos_retraso_gtfsrt/hora_llegada_gtfsrt (estación
    final del sentido: Chamartín para Madrid, Zamora para Galicia) y
    hora_paso_zamora_gtfsrt (paso por Zamora específicamente, para ambos
    sentidos — mismo papel que el campo ya existente hora_paso_zamora).
    Devuelve un dict listo para pasar como **kwargs a _mark_done; vacío si no
    hay coincidencia fiable o el enriquecimiento está desactivado.
    """
    entities = _fetch_gtfsrt_entities(log_extra)
    if not entities:
        return {}

    fields = {}
    endpoint_match = find_stop_time_update(entities, cod, endpoint_station_code, log_extra)
    if endpoint_match:
        if "minutos_retraso" in endpoint_match:
            fields["minutos_retraso_gtfsrt"] = endpoint_match["minutos_retraso"]
        if "hora_llegada" in endpoint_match:
            fields["hora_llegada_gtfsrt"] = endpoint_match["hora_llegada"]

    if sentido == "Madrid" and endpoint_station_code != ZAMORA_CODE:
        zamora_match = find_stop_time_update(entities, cod, ZAMORA_CODE, log_extra)
        if zamora_match and "hora_llegada" in zamora_match:
            fields["hora_paso_zamora_gtfsrt"] = zamora_match["hora_llegada"]
    elif "hora_llegada_gtfsrt" in fields:
        # Sentido Galicia: Zamora ES la estación final, mismo evento (igual
        # que hora_paso_zamora == hora_llegada_corregida en el dato existente).
        fields["hora_paso_zamora_gtfsrt"] = fields["hora_llegada_gtfsrt"]

    return fields


def _to_decimal(value) -> Decimal | None:
    """
    DynamoDB (vía boto3) no admite float nativo, solo Decimal. flotaLD.json
    entrega latitud/longitud como float tras el parseo JSON, así que hay que
    convertirlas antes de persistirlas. str(value) evita el ruido de
    precisión binaria que Decimal(float) arrastraría directamente.
    """
    return None if value is None else Decimal(str(value))


def _process_train(scheduled: dict, live: dict | None, today: date, now_local: datetime, log_extra: dict) -> bool:
    """
    Decide si procede marcar el tren como entregado.

    - Sentido Madrid: se entrega cuando el tren llega a Madrid Chamartín, es decir
      cuando desaparece de la flota (habiendo sido visto antes) o cuando
      `codEstAnt == CHAMARTIN_CODE`.
    - Resto de sentidos (Galicia): se entrega al pasar por Zamora
      (`codEstAnt == ZAMORA_CODE`).

    Devuelve True si el tren se marcó como entregado en DynamoDB.

    `today` es el día OPERATIVO (ver _operational_date), usado para el pk en
    DynamoDB; `now_local` es el instante real, usado para timestamps y para
    anclar las horas programadas vía _schedule_datetime.
    """
    cod = scheduled["cod_comercial"]

    if scheduled["sentido"] == "Madrid":
        return _process_madrid_train(scheduled, live, today, now_local, log_extra)

    # ── Sentido Galicia: grabar al pasar por Zamora, ventana sin cierre por
    # tiempo (se sigue intentando hasta capturarlo) ──────────────────────────
    state = _get_state(cod, today)
    if state and state.get("entregado"):
        return False

    if live is None:
        logger.warning("Tren %s (%s)no encontrado en flota (¿aún no ha salido?)", cod, scheduled["sentido"], extra=log_extra)
        return False

    cod_est_ant = live.get("codEstAnt", "")
    ult_retraso = int(live.get("ultRetraso", 0) or 0)
    ult_retraso, retraso_anomalo_alertado = _sanitize_retraso(
        cod, scheduled["sentido"], ult_retraso, scheduled["hora_llegada_destino"], today, now_local, log_extra,
        scheduled.get("offset_dias_llegada", 0),
        ya_alertado=bool(state and state.get("retraso_anomalo_alertado")),
    )
    latitud = _to_decimal(live.get("latitud"))
    longitud = _to_decimal(live.get("longitud"))

    # ── ¿Ya pasó por Zamora? ─────────────────────────────────────────────────
    if cod_est_ant == ZAMORA_CODE:
        # Para sentido Galicia, hora_llegada_destino es el paso programado por
        # Zamora (no el destino final en Galicia, que este sistema no seguía
        # nunca): hora_llegada_corregida ES la hora de paso por Zamora.
        h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
        hora_llegada_corregida = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=ult_retraso)
        ).strftime("%H:%M")

        gtfsrt_fields = _enrich_with_gtfsrt(cod, "Galicia", ZAMORA_CODE, log_extra)
        _mark_done(
            cod, today, now_local,
            hora_llegada_corregida=hora_llegada_corregida,
            hora_paso_zamora=hora_llegada_corregida,
            capturado_en_zamora=True,
            ult_retraso=ult_retraso,
            latitud=latitud,
            longitud=longitud,
            **gtfsrt_fields,
        )
        _maybe_publish_delay_alert(scheduled, ult_retraso, hora_llegada_corregida, today, now_local, log_extra)
        logger.info("✅ Tren %s (Galicia) entregado, retraso=%d min", cod, ult_retraso, extra=log_extra)
        return True

    # ── Todavía no ha llegado: actualizar estado en DynamoDB ─────────────────
    _update_state(
        cod, scheduled, ult_retraso, today, now_local, latitud=latitud, longitud=longitud,
        retraso_anomalo_alertado=retraso_anomalo_alertado,
    )
    logger.info(
        "Tren %s aún no en Zamora (última est: %s, retraso: %d min)",
        cod, cod_est_ant, ult_retraso,
        extra=log_extra
    )
    return False


def _process_madrid_train(scheduled: dict, live: dict | None, today: date, now_local: datetime, log_extra: dict) -> bool:
    """
    Lógica específica para trenes con sentido Madrid: el evento se graba cuando
    el tren ha llegado a Madrid Chamartín.

    Llegada detectada por cualquiera de estas dos vías:
      1. El tren ya no aparece en la flota, habiendo sido visto en una ejecución
         anterior (existe estado en DynamoDB), y ya se ha alcanzado
         hora_llegada_destino + último retraso conocido.
      2. `codEstAnt == CHAMARTIN_CODE`.

    Si la ventana se cierra sin ninguna de las dos detecciones, se resuelve
    aparte en _resolve_expired_madrid_trains(). `today` (día operativo) ancla
    hora_llegada_programada vía _schedule_datetime — necesario en el tramo de
    madrugada, donde now_local ya está en el día calendario siguiente.
    """
    cod   = scheduled["cod_comercial"]
    state = _get_state(cod, today)

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

            hora_llegada_programada = _schedule_datetime(
                today, scheduled["hora_llegada_destino"], now_local.tzinfo,
                scheduled.get("offset_dias_llegada", 0),
            )
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
            gtfsrt_fields = _enrich_with_gtfsrt(cod, "Madrid", CHAMARTIN_CODE, log_extra)
            _mark_done(cod, today, now_local, **gtfsrt_fields)
            _maybe_publish_delay_alert(
                scheduled, ult_retraso_conocido, state.get("hora_llegada_corregida"), today, now_local, log_extra
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
    ult_retraso, retraso_anomalo_alertado = _sanitize_retraso(
        cod, scheduled["sentido"], ult_retraso, scheduled["hora_llegada_destino"], today, now_local, log_extra,
        scheduled.get("offset_dias_llegada", 0),
        ya_alertado=bool(state and state.get("retraso_anomalo_alertado")),
    )
    latitud = _to_decimal(live.get("latitud"))
    longitud = _to_decimal(live.get("longitud"))

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

        gtfsrt_fields = _enrich_with_gtfsrt(cod, "Madrid", CHAMARTIN_CODE, log_extra)
        _mark_done(
            cod, today, now_local,
            hora_llegada_corregida=hora_llegada_corregida,
            capturado_en_zamora=capturado_en_zamora,
            ult_retraso=ult_retraso,
            latitud=latitud,
            longitud=longitud,
            **gtfsrt_fields,
        )
        _maybe_publish_delay_alert(scheduled, ult_retraso, hora_llegada_corregida, today, now_local, log_extra)
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
        cod, scheduled, ult_retraso, today, now_local,
        capturado_en_zamora=capturado_en_zamora,
        hora_paso_zamora=hora_paso_zamora,
        latitud=latitud,
        longitud=longitud,
        retraso_anomalo_alertado=retraso_anomalo_alertado,
    )
    logger.info(
        "Tren %s (Madrid) aún en ruta (última est: %s, retraso: %d min)",
        cod, cod_est_ant, ult_retraso, extra=log_extra
    )
    return False


def _get_state(cod: str, today: date) -> dict | None:
    """Recupera el estado transitorio del tren en DynamoDB (o None si no existe)."""
    resp = state_table.get_item(
        Key={"pk": f"{cod}#{today.isoformat()}"}
    )
    return resp.get("Item")


def _end_of_day_ttl(today: date) -> int:
    """
    TTL en epoch seconds: STATE_TTL_CUTOFF_HHMM del día siguiente a `today`
    (hora local) MÁS STATE_TTL_MARGIN_DAYS días completos — p. ej. la 01:30
    de today+2 con los valores por defecto.

    El estado de un día solo hace falta hasta que daily_dump_handler lo
    vuelca a S3 (01:00 del día siguiente), pero el margen es deliberadamente
    generoso y no ajustado a esa hora: el barrido de TTL de DynamoDB es
    best-effort, el volcado puede fallar y reintentarse, y sobre todo un
    cambio de la propia fórmula del TTL desplegado a media tarde deja los
    items ya escritos ese día con el corte anterior — que es exactamente lo
    que pasó el 2026-09-18 (ver STATE_TTL_CUTOFF_HHMM). Con un día entero de
    margen, ninguno de esos tres casos puede hacer desaparecer el estado
    antes de volcarlo.
    """
    cutoff_day = today + timedelta(days=1 + STATE_TTL_MARGIN_DAYS)
    hour, minute = (int(part) for part in STATE_TTL_CUTOFF_HHMM.split(":"))
    cutoff = datetime(
        cutoff_day.year, cutoff_day.month, cutoff_day.day,
        hour=hour, minute=minute, second=0, microsecond=0,
        tzinfo=ZoneInfo("Europe/Madrid"),
    )
    return int(cutoff.timestamp())


def _update_state(cod: str, scheduled: dict, retraso: int, today: date,
                  now_local: datetime, capturado_en_zamora: bool = False,
                  hora_paso_zamora: str | None = None,
                  latitud: str | None = None, longitud: str | None = None,
                  retraso_anomalo_alertado: bool = False):
    """
    Persiste el estado transitorio del tren en DynamoDB (pk indexado por
    `today`, el día operativo).

    put_item reemplaza el item entero, así que `retraso_anomalo_alertado`
    (una vez True) debe reenviarse en cada ciclo mientras el tren siga sin
    'entregado' — si no, se perdería en el siguiente put_item y
    _sanitize_retraso volvería a alertar por email en el ciclo siguiente.
    """
    ttl = _end_of_day_ttl(today)

    h, m = map(int, scheduled["hora_llegada_destino"].split(":"))
    hora_llegada_corregida = (
        datetime(2000, 1, 1, h, m) + timedelta(minutes=int(retraso))
    ).strftime("%H:%M")

    item = {
        "pk":          f"{cod}#{today.isoformat()}",
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
    # capturado, o Renfe no informó posición en este ciclo), se omite el
    # atributo en vez de fabricar un valor.
    if hora_paso_zamora is not None:
        item["hora_paso_zamora"] = hora_paso_zamora
    if latitud is not None:
        item["latitud"] = latitud
    if longitud is not None:
        item["longitud"] = longitud
    if retraso_anomalo_alertado:
        item["retraso_anomalo_alertado"] = True

    state_table.put_item(Item=item)


def _mark_done(cod: str, today: date, now_local: datetime, hora_llegada_corregida: str | None = None,
               capturado_en_zamora: bool | None = None, ult_retraso: int | None = None,
               hora_paso_zamora: str | None = None, minutos_retraso_gtfsrt: int | None = None,
               hora_llegada_gtfsrt: str | None = None, hora_paso_zamora_gtfsrt: str | None = None,
               latitud: str | None = None, longitud: str | None = None):
    """Marca el tren como entregado (procesado) para `today` (día operativo)."""
    # "ttl" es palabra reservada en DynamoDB → hay que usar un alias (#ttl).
    # Se fija siempre aquí, ya que este item puede no haber pasado nunca por
    # _update_state (p. ej. llegada detectada en el primer poll del tren).
    set_parts = ["entregado = :entregado", "#ttl = :ttl"]
    values = {":entregado": True, ":ttl": _end_of_day_ttl(today)}
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

    if minutos_retraso_gtfsrt is not None:
        set_parts.append("minutos_retraso_gtfsrt = :minutos_retraso_gtfsrt")
        values[":minutos_retraso_gtfsrt"] = minutos_retraso_gtfsrt

    if hora_llegada_gtfsrt is not None:
        set_parts.append("hora_llegada_gtfsrt = :hora_llegada_gtfsrt")
        values[":hora_llegada_gtfsrt"] = hora_llegada_gtfsrt

    if hora_paso_zamora_gtfsrt is not None:
        set_parts.append("hora_paso_zamora_gtfsrt = :hora_paso_zamora_gtfsrt")
        values[":hora_paso_zamora_gtfsrt"] = hora_paso_zamora_gtfsrt

    if latitud is not None:
        set_parts.append("latitud = :latitud")
        values[":latitud"] = latitud

    if longitud is not None:
        set_parts.append("longitud = :longitud")
        values[":longitud"] = longitud

    state_table.update_item(
        Key={"pk": f"{cod}#{today.isoformat()}"},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def _maybe_publish_delay_alert(scheduled: dict, ult_retraso: int,
                                hora_llegada_corregida: str | None,
                                today: date, now_local: datetime, log_extra: dict) -> None:
    """
    Publica un evento en SNS cuando un tren se acaba de marcar entregado con
    más de DELAY_ALERT_THRESHOLD_MINUTES minutos de retraso, para que
    tweet_notifier lo recoja y publique el tuit correspondiente. Desacoplado
    vía SNS para que un fallo/lentitud de la API de X no afecte al ciclo de
    polling. Un fallo al publicar se loguea pero no debe tirar la Lambda: el
    tren ya ha quedado grabado como entregado antes de esta llamada.

    El tren FLAGSHIP_MADRID_TRAIN_CODE (el primer laborable hacia Madrid, eje
    central de la reivindicación del "tren madrugador") es la excepción: se
    publica siempre, tenga o no retraso, para que tweet_notifier pueda
    recordar la reivindicación cada día laborable.
    """
    es_tren_madrugador = scheduled["cod_comercial"] == FLAGSHIP_MADRID_TRAIN_CODE
    if not es_tren_madrugador and ult_retraso <= DELAY_ALERT_THRESHOLD_MINUTES:
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
                "fecha": today.isoformat(),
                "es_tren_madrugador": es_tren_madrugador,
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


def _sanitize_retraso(cod: str, sentido: str, ult_retraso: int, hora_referencia: str,
                       today: date, now_local: datetime, log_extra: dict,
                       offset_dias_referencia: int = 0, ya_alertado: bool = False) -> tuple[int, bool]:
    """
    Renfe ha reportado alguna vez un ultRetraso disparatado (p. ej. -562 min
    en flotaLD.json) — un fallo puntual de su servicio, no un tren circulando
    con adelanto real. Si el retraso cae por debajo de
    NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES no es fiable: se recalcula
    comparando la hora programada de referencia (hora_llegada_destino) con la
    hora actual. La corrección se propaga automáticamente a
    hora_llegada_corregida/hora_paso_zamora, que se calculan a partir de este
    mismo valor. `today` (día operativo) ancla esa hora programada vía
    _schedule_datetime — imprescindible en el tramo de madrugada, donde
    now_local ya está en el día calendario siguiente — y
    offset_dias_referencia la sitúa en el día correcto si el tren cruza la
    medianoche.

    Mientras el tren no se marca 'entregado' se reevalúa en cada ciclo de 5
    min, y el mismo bug de Renfe suele persistir varios ciclos seguidos: sin
    `ya_alertado` esto mandaría un email por ciclo (docenas al día). El
    llamador debe pasar el valor ya persistido en DynamoDB
    (`retraso_anomalo_alertado`) y volver a guardar el booleano devuelto, de
    forma que el aviso por email solo se publique la primera vez que se
    detecta la anomalía para ese tren+día; el resto del día se sigue
    corrigiendo el valor igual, solo se omite el email repetido.
    """
    if ult_retraso >= NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES:
        return ult_retraso, ya_alertado

    hora_programada = _schedule_datetime(
        today, hora_referencia, now_local.tzinfo, offset_dias_referencia
    )
    retraso_corregido = round((now_local - hora_programada).total_seconds() / 60)

    logger.warning(
        "Tren %s (%s): ultRetraso=%d es anómalo (< %d min), posible bug de la API de Renfe. "
        "Corregido a %d min comparando hora actual (%s) con hora programada (%s).",
        cod, sentido, ult_retraso, NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES,
        retraso_corregido, now_local.strftime("%H:%M"), hora_referencia,
        extra=log_extra,
    )
    if not ya_alertado:
        _publish_negative_delay_alert(cod, sentido, ult_retraso, retraso_corregido, now_local, log_extra)
    return retraso_corregido, True


def _publish_negative_delay_alert(cod: str, sentido: str, ult_retraso_original: int,
                                   ult_retraso_corregido: int, now_local: datetime,
                                   log_extra: dict) -> None:
    """
    Notifica por email (vía AlertTopic/SNS) un ultRetraso anómalo recibido de
    Renfe, para poder revisar manualmente si la corrección automática fue
    razonable. No bloquea el ciclo de polling si falla o si no hay email de
    alertas configurado (DATA_QUALITY_ALERT_SNS_TOPIC_ARN vacío).
    """
    if not DATA_QUALITY_ALERT_SNS_TOPIC_ARN:
        return

    try:
        sns.publish(
            TopicArn=DATA_QUALITY_ALERT_SNS_TOPIC_ARN,
            Subject=f"[Zamora Trains] Retraso negativo anómalo - tren {cod}",
            Message=(
                f"El tren {cod} ({sentido}) ha recibido un ultRetraso de "
                f"{ult_retraso_original} min desde la API de Renfe, posible bug del servicio.\n\n"
                f"Hora del evento: {now_local.isoformat()}\n"
                f"Retraso corregido automáticamente a: {ult_retraso_corregido} min "
                f"(estimado a partir de la hora actual)."
            ),
        )
        logger.info("Alerta de retraso negativo anómalo publicada para %s", cod, extra=log_extra)
    except Exception as exc:
        logger.error(
            "Error publicando alerta de retraso negativo anómalo para %s: %s",
            cod, exc, extra=log_extra
        )


def _publish_schedule_fallback_alert(message: str, log_extra: dict) -> None:
    """
    Notifica por email (vía AlertTopic/SNS, mismo topic que
    _publish_negative_delay_alert) que schedule_resolver.py ha tenido que
    recurrir al fichero estático de reserva en vez de resolver el horario
    del día desde GTFS. A diferencia de los enriquecimientos aditivos de
    este proyecto, el horario del día es crítico para saber qué trenes
    monitorizar, así que este aviso no es opcional aunque el email de
    alertas no esté configurado — solo se omite el envío en sí.
    """
    _publish_alert(
        "[Zamora Trains] Horario del día resuelto con fallback estático", message, log_extra
    )


def _publish_alert(subject: str, message: str, log_extra: dict) -> None:
    """
    Publica un aviso operativo por email vía AlertTopic/SNS
    (DATA_QUALITY_ALERT_SNS_TOPIC_ARN — el topic de revisión manual, nunca
    DelayTweetTopic, que solo debe recibir retrasos reales destinados al
    feed público). Nunca lanza: un fallo de SNS no debe tumbar el ciclo que
    lo invoca, y si no hay topic configurado el aviso queda al menos como
    logger.error.
    """
    if not DATA_QUALITY_ALERT_SNS_TOPIC_ARN:
        logger.error(
            "%s: %s (sin DATA_QUALITY_ALERT_SNS_TOPIC_ARN configurado, no se envía email)",
            subject, message, extra=log_extra,
        )
        return

    try:
        sns.publish(TopicArn=DATA_QUALITY_ALERT_SNS_TOPIC_ARN, Subject=subject, Message=message)
        logger.info("Alerta publicada: %s", subject, extra=log_extra)
    except Exception as exc:
        logger.error("Error publicando la alerta '%s': %s", subject, exc, extra=log_extra)


def _resolve_expired_madrid_trains(today: date, now_local: datetime, trains_today: list[dict], log_extra: dict) -> int:
    """
    Recorre los trenes Madrid con estado pendiente en DynamoDB (no 'entregado')
    cuya ventana (hora_llegada_destino + último retraso conocido + 10 min)
    ya se ha cerrado sin haber sido detectados como llegados (ni Chamartín ni
    desaparición), y los marca igualmente como entregados con los últimos
    datos conocidos para no perder el dato de puntualidad de ese tren ese día.
    `today` (día operativo) ancla hora_llegada_programada vía
    _schedule_datetime, para que la comparación siga siendo correcta durante
    el tramo de madrugada (ver _operational_date), cuando un tren con mucho
    retraso puede cerrar su ventana ya en el día calendario siguiente.

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
    for train in trains_today:
        if train["sentido"] != "Madrid":
            continue

        cod = train["cod_comercial"]
        state = _get_state(cod, today)
        if not state or state.get("entregado"):
            continue

        hora_llegada_programada = _schedule_datetime(
            today, train["hora_llegada_destino"], now_local.tzinfo,
            train.get("offset_dias_llegada", 0),
        )
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
        gtfsrt_fields = _enrich_with_gtfsrt(cod, "Madrid", CHAMARTIN_CODE, log_extra)
        _mark_done(cod, today, now_local, **gtfsrt_fields)
        logger.warning(
            "Tren %s (Madrid) ventana cerrada sin detección → entregado con "
            "últimos datos conocidos (retraso: %d min)", cod, ult_retraso_conocido, extra=log_extra
        )
        resolved += 1

    return resolved


def daily_dump_handler(event, context):
    """
    Lambda de volcado diario. Se ejecuta a la 01:00 (hora de Madrid), tras
    el tramo de polling de madrugada del día anterior (ver
    NIGHT_TAIL_WINDOW_MINUTES/_operational_date) y con un día entero de
    margen antes de que el TTL de DynamoDB (01:30 de fecha+2, ver
    _end_of_day_ttl) pueda barrer sus datos. Lee de DynamoDB todos los
    trenes programados el día que acaba de terminar (sembrados por
    _seed_todays_trains, que crea un item por cada uno) y los escribe en un
    único fichero JSONL en S3.

    Un tren que nunca llegó a marcarse 'entregado' (nunca detectado en
    flotaLD.json en todo el día, madrugada incluida) se vuelca igualmente
    como 'cancelado': true, con 'minutos_retraso'/'hora_llegada_corregida' a
    null — no hay dato real de retraso que reportar, y forzar un valor (p.
    ej. 0) contaminaría medias y estadísticas como si el tren hubiese
    circulado puntual.

    Esa lectura de 'entregado': False como cancelación solo es válida si el
    estado leído es el que se fue acumulando durante el día. Antes de
    escribir nada se comprueba el marcador SEED#{fecha} (ver
    _check_seed_marker): si falta, o se sembró un día distinto del volcado,
    el estado del día no es de fiar y se aborta con aviso en vez de publicar
    una jornada entera de cancelaciones falsas en el Data Lake — que es lo
    que ocurrió el 2026-09-18.
    """
    log_extra = {'span_id': context.aws_request_id}

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo("Europe/Madrid"))
    target_date = now_local.date() - timedelta(days=1)
    target_date_iso = target_date.isoformat()

    logger.info("Volcado diario iniciado para %s", target_date_iso, extra=log_extra)

    # Antes de leer nada: ¿es fiable el estado del día? (ver _check_seed_marker)
    reason = _check_seed_marker(target_date, log_extra)
    if reason is not None:
        return {"statusCode": 500, "written": 0, "reason": reason}

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
                "minutos_retraso_gtfsrt": (
                    int(item["minutos_retraso_gtfsrt"])
                    if entregado and item.get("minutos_retraso_gtfsrt") is not None
                    else None
                ),
                "hora_llegada_gtfsrt": item.get("hora_llegada_gtfsrt") if entregado else None,
                "hora_paso_zamora_gtfsrt": item.get("hora_paso_zamora_gtfsrt") if entregado else None,
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

    _alert_on_excessive_cancellations(records, target_date_iso, log_extra)

    # Best-effort: la tabla de métricas es una caché derivada del volcado a
    # S3, que sigue siendo la fuente de verdad. Un fallo aquí no debe afectar
    # al resultado del volcado diario, ya completado con éxito.
    try:
        MetricsWriter(metrics_table, SIGNIFICANT_DELAY_THRESHOLD_MINUTES, log_extra).update_daily_metrics(
            records, target_date, now_local
        )
    except Exception as exc:
        logger.error("Error actualizando métricas precalculadas para %s: %s", target_date_iso, exc, extra=log_extra)

    return {"statusCode": 200, "written": len(records), "key": key}


def _check_seed_marker(target_date: date, log_extra: dict) -> str | None:
    """
    Verifica que el estado que se va a volcar es el que se acumuló durante
    `target_date`, apoyándose en el marcador SEED#{fecha} que escribe
    _seed_todays_trains. Devuelve None si todo está en orden, o el motivo
    (str) por el que NO debe volcarse:

    - "seed_marker_missing": el marcador ya no está. Con el TTL actual
      sobrevive de sobra al volcado (ver _end_of_day_ttl), así que su
      ausencia significa que el estado del día ha expirado antes de tiempo;
      lo que quede en la tabla está incompleto.
    - "seed_marker_rebuilt": el marcador se escribió un día distinto del que
      se vuelca, es decir el día se resembró a posteriori. Los items serían
      placeholders recién creados y se volcarían como cancelados.

    Los marcadores escritos por versiones anteriores no llevan 'seeded_at';
    en ese caso solo se puede comprobar su existencia, y se da por bueno.
    """
    target_iso = target_date.isoformat()
    marker = state_table.get_item(Key={"pk": f"SEED#{target_iso}"}).get("Item")

    if marker is None:
        message = (
            f"Volcado diario del {target_iso} ABORTADO: no existe el marcador "
            f"SEED#{target_iso}, así que el estado del día ha expirado o se ha borrado "
            f"y lo que queda en DynamoDB está incompleto. No se escribe el fichero JSONL "
            f"para no registrar trenes como cancelados sin haberlos monitorizado."
        )
        logger.error(message, extra=log_extra)
        _publish_alert("[Zamora Trains] Volcado diario abortado: estado del día perdido", message, log_extra)
        return "seed_marker_missing"

    seeded_at = marker.get("seeded_at")
    if seeded_at and str(seeded_at)[:10] != target_iso:
        message = (
            f"Volcado diario del {target_iso} ABORTADO: su marcador SEED# se sembró el "
            f"{seeded_at}, fuera del propio día. El día se ha resembrado a posteriori, "
            f"así que los trenes en DynamoDB son placeholders y no el estado real del día."
        )
        logger.error(message, extra=log_extra)
        _publish_alert("[Zamora Trains] Volcado diario abortado: día resembrado", message, log_extra)
        return "seed_marker_rebuilt"

    return None


def _alert_on_excessive_cancellations(records: list[dict], target_date_iso: str, log_extra: dict) -> None:
    """
    Avisa (sin bloquear el volcado, que ya se ha escrito) si la proporción de
    trenes cancelados supera MAX_CANCELLED_RATIO_ALERT. Una huelga real puede
    dar un porcentaje altísimo y es un dato legítimo, así que esto no impide
    escribir el fichero: es una red de seguridad para enterarse el mismo día
    de que el polling no ha funcionado, en vez de descubrirlo semanas después
    consultando Athena.
    """
    cancelados = sum(1 for record in records if record["cancelado"])
    ratio = cancelados / len(records)
    if ratio <= MAX_CANCELLED_RATIO_ALERT:
        return

    message = (
        f"El volcado del {target_date_iso} ha registrado {cancelados} de {len(records)} "
        f"trenes como cancelados ({ratio:.0%}, umbral {MAX_CANCELLED_RATIO_ALERT:.0%}). "
        f"Si no hubo huelga ni incidencia general, revisar los logs del polling de ese día."
    )
    logger.warning(message, extra=log_extra)
    _publish_alert("[Zamora Trains] Proporción anómala de trenes cancelados", message, log_extra)
