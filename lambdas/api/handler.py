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
S3_PREFIX = "zamora-trains"

# flotaLD.json no envía cabeceras CORS, así que el frontend no puede
# consultarlo directamente desde el navegador: este handler solo reenvía la
# respuesta añadiendo Access-Control-Allow-Origin (ver _json_response).
FLOTA_URL = "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json"

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

state_table = dynamodb.Table(DYNAMODB_TABLE)


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
