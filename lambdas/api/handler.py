import calendar
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

import boto3

logger = logging.getLogger("api")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

S3_BUCKET = os.environ["DATALAKE_S3_BUCKET"]
DYNAMODB_TABLE = os.environ["DYNAMODB_STATE_TABLE"]
DYNAMODB_METRICS_TABLE = os.environ["DYNAMODB_METRICS_TABLE"]
SIGNIFICANT_DELAY_THRESHOLD_MINUTES = int(os.environ.get("SIGNIFICANT_DELAY_THRESHOLD_MINUTES", "15"))
SCHEDULES_FILE = os.environ.get("SCHEDULES_FILE", "/var/task/train_schedules.json")
S3_PREFIX = "zamora-trains"

with open(SCHEDULES_FILE, "r", encoding="utf-8") as fh:
    schedules_config = json.load(fh)

# flotaLD.json no envía cabeceras CORS, así que el frontend no puede
# consultarlo directamente desde el navegador: este handler solo reenvía la
# respuesta añadiendo Access-Control-Allow-Origin (ver _json_response).
FLOTA_URL = "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json"

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

state_table = dynamodb.Table(DYNAMODB_TABLE)
metrics_table = dynamodb.Table(DYNAMODB_METRICS_TABLE)


def _build_train_schedule_index(trains: list[dict]) -> list[dict]:
    """
    Une, por cod_comercial, los weekdays (0=lunes..6=domingo) de todas sus
    filas de horario (un tren puede tener varias filas, una por tipo_dia).
    Se calcula una sola vez al importar el módulo — no cambia entre
    invocaciones de la Lambda.
    """
    by_cod: dict[str, dict] = {}
    for train in trains:
        cod = train["cod_comercial"]
        entry = by_cod.setdefault(
            cod,
            {
                "cod_comercial": cod,
                "sentido": train["sentido"],
                "hora_salida": train["hora_salida"],
                "hora_llegada_destino": train["hora_llegada_destino"],
                "weekdays": set(),
            },
        )
        entry["weekdays"].update(train["weekdays"])
    return [
        {
            "cod_comercial": cod,
            "sentido": entry["sentido"],
            "hora_salida": entry["hora_salida"],
            "hora_llegada_destino": entry["hora_llegada_destino"],
            "weekdays": sorted(entry["weekdays"]),
        }
        for cod, entry in sorted(by_cod.items())
    ]


TRAIN_SCHEDULE_INDEX = _build_train_schedule_index(schedules_config["trains"])


def _parse_date_param(event: dict) -> date | None:
    date_str = (event.get("pathParameters") or {}).get("date")
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


def _scan_trains_for_date(date_iso: str) -> list[dict]:
    records = []
    scan_kwargs = {"FilterExpression": "attribute_exists(cod_comercial)"}
    while True:
        resp = state_table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            if item["pk"].endswith(f"#{date_iso}"):
                records.append(item)
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return records


TODAY_ITEM_FIELDS = (
    "cod_comercial",
    "sentido",
    "tipo_dia",
    "hora_programada",
    "hora_llegada_corregida",
    "hora_paso_zamora",
    "ult_retraso",
    "capturado_en_zamora",
    "entregado",
    "updated_at",
)


def _project_today_item(item: dict) -> dict:
    return {field: item.get(field) for field in TODAY_ITEM_FIELDS}


def _build_daily_key(day: date) -> str:
    year, month, day_s = day.strftime("%Y"), day.strftime("%m"), day.strftime("%d")
    return f"{S3_PREFIX}/year={year}/month={month}/day={day_s}/{day.isoformat()}.jsonl"


def _json_response(status: int, payload) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(payload, ensure_ascii=False, default=str),
    }


def get_today_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    from zoneinfo import ZoneInfo
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo("Europe/Madrid"))
    today_iso = now_local.date().isoformat()

    items = _scan_trains_for_date(today_iso)
    trains = [_project_today_item(item) for item in items]

    logger.info("get_today_handler: %d trenes para %s", len(trains), today_iso, extra=log_extra)
    return _json_response(200, trains)


def get_day_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    target_date = _parse_date_param(event)
    if target_date is None:
        return _json_response(400, {"error": "fecha inválida, se espera YYYY-MM-DD"})

    key = _build_daily_key(target_date)
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
    except s3.exceptions.NoSuchKey:
        logger.info("get_day_handler: %s aún no volcado (%s)", target_date.isoformat(), key, extra=log_extra)
        return _json_response(404, {"error": "no hay datos para esa fecha todavía"})

    body = response["Body"].read().decode("utf-8")
    trains = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        trains.append(json.loads(line))

    logger.info("get_day_handler: %d trenes para %s", len(trains), target_date.isoformat(), extra=log_extra)
    return _json_response(200, trains)


def _scan_metrics_by_prefix(prefix: str) -> list[dict]:
    items = []
    scan_kwargs = {
        "FilterExpression": "begins_with(pk, :prefix)",
        "ExpressionAttributeValues": {":prefix": prefix},
    }
    while True:
        resp = metrics_table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def _pct(part, total) -> float:
    return round((int(part) / int(total)) * 100, 2)


_DELAY_BUCKET_KEYS = ("puntual", "leve", "significativo", "grave")


def _project_delay_buckets(item: dict) -> dict:
    """
    Deriva los 4 tramos de retraso (+ sus porcentajes) y el "retraso
    significativo" agregado (tramos significativo+grave) a partir de los
    contadores brutos de nivel superior de un item TRAIN#/WEEK#/MONTH#/
    GLOBAL. Nada de esto se guarda en DynamoDB: se recalcula en cada
    lectura sobre, como mucho, un puñado de trenes/periodos.
    """
    total = int(item["total_viajes"])
    buckets = {key: int(item[f"viajes_bucket_{key}"]) for key in _DELAY_BUCKET_KEYS}
    significativos = buckets["significativo"] + buckets["grave"]

    result = {
        "total_viajes": total,
        "suma_retraso_significativo_minutos": int(item["suma_retraso_significativo_minutos"]),
        "viajes_retraso_significativo": significativos,
        "pct_retraso_significativo": _pct(significativos, total),
    }
    for key in _DELAY_BUCKET_KEYS:
        result[f"viajes_bucket_{key}"] = buckets[key]
        result[f"pct_bucket_{key}"] = _pct(buckets[key], total)
    return result


def _rank_por_tren(por_tren: dict) -> list[dict]:
    """Ordena los trenes de un periodo (semana/mes) por % de retraso significativo, descendente."""
    ranked = []
    for cod, bucket in por_tren.items():
        total = int(bucket["total_viajes"])
        significativos = int(bucket["viajes_retraso_significativo"])
        ranked.append({
            "cod_comercial": cod,
            "total_viajes": total,
            "viajes_retraso_significativo": significativos,
            "pct_retraso_significativo": _pct(significativos, total),
        })
    ranked.sort(key=lambda t: (-t["pct_retraso_significativo"], t["cod_comercial"]))
    return ranked


def _rank_por_dia_semana(por_dia_semana: dict) -> list[dict]:
    """Ordena los días de la semana de un periodo por % de retraso significativo, descendente."""
    ranked = []
    for weekday_str, bucket in por_dia_semana.items():
        total = int(bucket["total_viajes"])
        significativos = int(bucket["viajes_retraso_significativo"])
        ranked.append({
            "dia_semana": int(weekday_str),
            "total_viajes": total,
            "viajes_retraso_significativo": significativos,
            "suma_retraso_significativo_minutos": int(bucket["suma_retraso_significativo_minutos"]),
            "pct_retraso_significativo": _pct(significativos, total),
        })
    ranked.sort(key=lambda d: (-d["pct_retraso_significativo"], d["dia_semana"]))
    return ranked


def _rank_por_franja_horaria(por_franja_horaria: dict) -> list[dict]:
    """Ordena las franjas horarias (mañana/tarde/noche) por % de retraso significativo, descendente."""
    ranked = []
    for franja, bucket in por_franja_horaria.items():
        total = int(bucket["total_viajes"])
        significativos = int(bucket["viajes_retraso_significativo"])
        ranked.append({
            "franja": franja,
            "total_viajes": total,
            "viajes_retraso_significativo": significativos,
            "suma_retraso_significativo_minutos": int(bucket["suma_retraso_significativo_minutos"]),
            "pct_retraso_significativo": _pct(significativos, total),
        })
    ranked.sort(key=lambda f: (-f["pct_retraso_significativo"], f["franja"]))
    return ranked


def _project_period_item(item: dict) -> dict:
    """
    Deriva tramos/porcentajes y extremos (tren/día de la semana más y menos
    probable de sufrir retraso significativo) a partir de los contadores
    brutos acumulados en un item WEEK#/MONTH#.

    dia_semana_con_mas_retrasos usa el RECUENTO bruto de viajes con retraso
    significativo ese día (lo que pidió el usuario como "más retrasos"),
    distinto de dia_semana_mas_probable/menos_probable que usan la TASA (%) —
    en el mensual, donde cada día de la semana ocurre varias veces, ambos
    pueden señalar días distintos.
    """
    tren_ranking = _rank_por_tren(item.get("por_tren") or {})
    dia_ranking_por_tasa = _rank_por_dia_semana(item.get("por_dia_semana") or {})
    dia_ranking_por_recuento = sorted(
        dia_ranking_por_tasa, key=lambda d: (-d["viajes_retraso_significativo"], d["dia_semana"])
    )

    return {
        **_project_delay_buckets(item),
        "tren_mas_probable": tren_ranking[0] if tren_ranking else None,
        "tren_menos_probable": tren_ranking[-1] if tren_ranking else None,
        "dia_semana_con_mas_retrasos": dia_ranking_por_recuento[0] if dia_ranking_por_recuento else None,
        "dia_semana_mas_probable": dia_ranking_por_tasa[0] if dia_ranking_por_tasa else None,
        "dia_semana_menos_probable": dia_ranking_por_tasa[-1] if dia_ranking_por_tasa else None,
    }


def _ranked_trains() -> list[dict]:
    """
    Escanea TRAIN# y ordena por % de retraso significativo, descendente
    (rank_retraso=1 = el más propenso). Compartido por get_train_metrics_handler
    y get_global_metrics_handler (para "tren con más riesgo") — evita
    duplicar el cálculo y una segunda llamada del frontend.
    """
    items = _scan_metrics_by_prefix("TRAIN#")
    trains = []
    for item in items:
        trains.append({
            "cod_comercial": item["cod_comercial"],
            "sentido": item["sentido"],
            **_project_delay_buckets(item),
        })

    # Empates: orden estable por cod_comercial.
    trains.sort(key=lambda t: (-t["pct_retraso_significativo"], t["cod_comercial"]))
    for rank, train in enumerate(trains, start=1):
        train["rank_retraso"] = rank
        train["total_trenes_comparados"] = len(trains)

    return trains


def get_train_metrics_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    trains = _ranked_trains()

    logger.info("get_train_metrics_handler: %d trenes", len(trains), extra=log_extra)
    return _json_response(200, trains)


def get_week_metrics_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    from zoneinfo import ZoneInfo
    today_local = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Madrid")).date()

    items = _scan_metrics_by_prefix("WEEK#")
    weeks = []
    for item in items:
        week_end = date.fromisoformat(item["week_end"])
        weeks.append({
            "iso_year": int(item["iso_year"]),
            "iso_week": int(item["iso_week"]),
            "week_start": item["week_start"],
            "week_end": item["week_end"],
            "is_complete": today_local > week_end,
            **_project_period_item(item),
        })

    weeks.sort(key=lambda w: (w["iso_year"], w["iso_week"]))

    logger.info("get_week_metrics_handler: %d semanas", len(weeks), extra=log_extra)
    return _json_response(200, weeks)


def get_month_metrics_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    from zoneinfo import ZoneInfo
    today_local = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Madrid")).date()

    items = _scan_metrics_by_prefix("MONTH#")
    months = []
    for item in items:
        year, month = int(item["year"]), int(item["month"])
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        months.append({
            "year": year,
            "month": month,
            "is_complete": today_local > month_end,
            **_project_period_item(item),
        })

    months.sort(key=lambda m: (m["year"], m["month"]))

    logger.info("get_month_metrics_handler: %d meses", len(months), extra=log_extra)
    return _json_response(200, months)


def get_global_metrics_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    item = metrics_table.get_item(Key={"pk": "GLOBAL"}).get("Item")
    if item is None:
        logger.info("get_global_metrics_handler: aún no hay métricas globales", extra=log_extra)
        return _json_response(404, {"error": "no hay métricas todavía"})

    dia_ranking = _rank_por_dia_semana(item.get("por_dia_semana") or {})
    franja_ranking = _rank_por_franja_horaria(item.get("por_franja_horaria") or {})
    tren_ranking = _ranked_trains()

    response = {
        **_project_delay_buckets(item),
        "first_aggregated_date": item["first_aggregated_date"],
        "significant_delay_threshold_minutes": SIGNIFICANT_DELAY_THRESHOLD_MINUTES,
        "dia_semana_mas_probable": dia_ranking[0] if dia_ranking else None,
        "dia_semana_menos_probable": dia_ranking[-1] if dia_ranking else None,
        "franja_horaria_mas_probable": franja_ranking[0] if franja_ranking else None,
        "tren_mas_probable": tren_ranking[0] if tren_ranking else None,
        "tren_menos_probable": tren_ranking[-1] if tren_ranking else None,
    }

    logger.info("get_global_metrics_handler: métricas globales servidas", extra=log_extra)
    return _json_response(200, response)


def get_train_schedule_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    logger.info("get_train_schedule_handler: %d trenes", len(TRAIN_SCHEDULE_INDEX), extra=log_extra)
    return _json_response(200, TRAIN_SCHEDULE_INDEX)


def get_flota_handler(event, context):
    log_extra = {'span_id': context.aws_request_id}

    req = urllib.request.Request(
        FLOTA_URL,
        headers={
            "User-Agent": "ZamoraTrainObservability/1.0 (AWS Lambda proxy)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        logger.error("get_flota_handler: fallo al contactar Renfe: %s", exc, extra=log_extra)
        return _json_response(502, {"error": "no se pudo obtener la posición en tiempo real de Renfe"})

    data = json.loads(raw)
    trenes = data.get("trenes") or [] if isinstance(data, dict) else []
    logger.info("get_flota_handler: proxy de flotaLD.json (%d trenes)", len(trenes), extra=log_extra)
    return _json_response(200, data)
