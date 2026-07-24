"""
handler.py — Lambda: train-tracker
Ejecutada cada 5 minutos por EventBridge Scheduler.

Lógica:
1. Determinar qué trenes tienen ventana activa ahora mismo (±30 min respecto
   a su hora de paso programada por Zamora).
2. Descargar flotaLD.json de Renfe.
3. Para cada tren activo, buscar su entrada en la flota.
4. Punto de grabación en S3 según el sentido:
   - Galicia: cuando pasa por Zamora (codEstAnt == ZAMORA_CODE).
   - Madrid: cuando llega a Madrid Chamartín, detectado porque el tren
     desaparece de la flota (habiendo sido visto antes) o porque
     codEstAnt == CHAMARTIN_CODE.
5. Si aún no ha llegado → actualizar estado en DynamoDB (se revisará
   en la próxima ejecución en 5 min).
6. Si hay retraso acumulado, ajustar la ventana de monitorización.
"""

import json
import logging
import os
from datetime import datetime, timezone

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

    # 1. ¿Qué trenes tienen ventana activa ahora?
    active_trains = matcher.get_active_trains(now_local)
    if not active_trains:
        logger.info("No hay trenes en ventana activa. Saliendo.")
        return {"statusCode": 200, "active": 0}

    logger.debug("Trenes en ventana activa: %s", [t["cod_comercial"] for t in active_trains])

    # 2. Descargar flota en tiempo real
    try:
        flota = renfe_client.get_flota()
    except Exception as exc:
        logger.error("Error descargando flotaLD.json: %s", exc)
        # No hay que fallar la Lambda; se reintentará en 5 min
        return {"statusCode": 503, "error": str(exc)}

    # Indexar flota por codComercial para O(1) lookup
    flota_index = {t.get("codComercial", ""): t for t in flota}

    processed = 0
    for scheduled_train in active_trains:
        cod = scheduled_train["cod_comercial"]
        # train_data puede ser None (tren no presente en la flota). Para los
        # trenes con sentido Madrid esa ausencia es significativa (llegada a
        # Chamartín), por eso lo delegamos siempre en _process_train.
        train_data = flota_index.get(cod)

        result = _process_train(scheduled_train, train_data, now_local)
        if result:
            processed += 1

    logger.info("Trenes procesados y grabados: %d / %d activos", processed, len(active_trains))
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

    # ── Sentido Galicia: comportamiento original (grabar al pasar por Zamora) ─
    if live is None:
        logger.warning("Tren %s no encontrado en flota (¿aún no ha salido?)", cod)
        return False

    cod_est_ant = live.get("codEstAnt", "")
    ult_retraso = int(live.get("ultRetraso", 0) or 0)

    # ── ¿Ya pasó por Zamora? ─────────────────────────────────────────────────
    if cod_est_ant == ZAMORA_CODE:
        _record_passage(scheduled, live, now_local)

        from datetime import timedelta
        h, m = map(int, scheduled["hora_paso_zamora"].split(":"))
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
         anterior (existe estado en DynamoDB).
      2. `codEstAnt == CHAMARTIN_CODE`.
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
            from datetime import timedelta

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

            # Algunos trenes desaparecen de la flota antes de llegar realmente
            # a destino (hueco de cobertura GPS, cambio de composición, etc.).
            # Para evitar falsos positivos, solo se empieza a contar reintentos
            # si la desaparición ocurre a partir de 10 min antes de la hora
            # programada; si es más pronto, se reintenta en la próxima ejecución,
            # con un límite de reintentos = floor(ult_retraso / 5) (mínimo 1)
            # antes de darlo por llegado igualmente con los últimos datos conocidos.
            if now_local >= hora_llegada_programada - timedelta(minutes=10):
                ult_retraso_conocido = int(state.get("ult_retraso", 0) or 0)
                max_reintentos = max(1, ult_retraso_conocido // 5)
                reintentos = int(state.get("retries", 0) or 0)

                if reintentos < max_reintentos:
                    _increment_retry_count(cod, now_local)
                    logger.warning(
                        "Tren %s (Madrid) desaparecido de la flota demasiado pronto "
                        "(hora actual: %s, hora programada: %s) → reintento %d/%d, "
                        "no se da por llegado todavía",
                        cod, now_local.strftime("%H:%M"), scheduled["hora_llegada_destino"],
                        reintentos + 1, max_reintentos
                    )
                    return False

                logger.warning(
                    "Tren %s (Madrid) agotó los %d reintentos tras desaparecer "
                    "antes de hora → se da por llegado con los últimos datos conocidos",
                    cod, max_reintentos
                )
            else:
                logger.warning(
                    "Tren %s (Madrid) desaparecido de la flota pero aún no ha "
                    "llegado (hora actual: %s, hora programada: %s)",
                    cod, now_local.strftime("%H:%M"), scheduled["hora_llegada_destino"]
                )
                return False

            # No hay datos en vivo; usamos el último estado conocido.
            last_known = {
                "ultRetraso": state.get("ult_retraso", 0),
                "codEstAnt":  state.get("cod_est_ant"),
            }
            _record_passage(scheduled, last_known, now_local)
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
        _record_passage(scheduled, live, now_local)
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


def _record_passage(scheduled: dict, live: dict, now_local: datetime):
    """Construye el registro del datalake y lo escribe en S3."""
    ult_retraso = int(live.get("ultRetraso", 0) or 0)
    hora_programada = scheduled["hora_llegada_destino"]  # "HH:MM"
    h, m = map(int, hora_programada.split(":"))
    from datetime import timedelta
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
        "ult_retraso_renfe": ult_retraso
    }

    writer.write(record, now_local)
    logger.info("✅ Grabado: %s retraso=%d min", record["event_id"], ult_retraso)


def _update_state(cod: str, scheduled: dict, retraso: int,
                  cod_est_ant: str, now_local: datetime, capturado_en_zamora: bool = False):
    """Persiste el estado transitorio del tren en DynamoDB."""
    import time
    from datetime import timedelta
    ttl = int(time.time()) + 86400  # expira en 24h

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
    set_parts = ["done = :done"]
    values = {":done": True}

    if hora_llegada_real is not None:
        set_parts.append("hora_llegada_real = :hora_real")
        values[":hora_real"] = hora_llegada_real

    if capturado_en_zamora is not None:
        set_parts.append("capturado_en_zamora = :capturado")
        values[":capturado"] = capturado_en_zamora

    state_table.update_item(
        Key={"pk": f"{cod}#{now_local.date().isoformat()}", "sk": "TRACKING"},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeValues=values,
    )


def _increment_retry_count(cod: str, now_local: datetime):
    """Incrementa el contador de reintentos por desaparición prematura de la flota."""
    state_table.update_item(
        Key={"pk": f"{cod}#{now_local.date().isoformat()}", "sk": "TRACKING"},
        UpdateExpression="ADD retries :one",
        ExpressionAttributeValues={":one": 1},
    )
