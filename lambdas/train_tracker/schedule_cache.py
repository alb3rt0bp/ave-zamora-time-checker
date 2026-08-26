"""
schedule_cache.py
Cachea en S3 el horario del día ya resuelto desde GTFS (ver gtfs_client.py /
gtfs_schedule_builder.py), para no descargar y parsear el zip de Renfe en
cada uno de los ~180 ciclos de polling del día — solo en el primero que no
lo encuentre ya cacheado. Un objeto por día (schedules/{fecha}.json), mismo
espíritu que trends/latest_hashtags.json de trend_fetcher, pero sin concepto
de caducidad: la fecha va en la propia clave, así que "existe" y "es de hoy"
son la misma pregunta.
"""

import json
import logging
import os
from datetime import date, datetime, timezone

from botocore.exceptions import ClientError

logger = logging.getLogger(f"train_tracker.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

SCHEDULES_S3_PREFIX = os.environ.get("SCHEDULES_S3_PREFIX", "schedules/")


def _key_for(target_date: date) -> str:
    return f"{SCHEDULES_S3_PREFIX}{target_date.isoformat()}.json"


def get_cached_schedule(s3, bucket: str, target_date: date, log_extra: dict) -> list[dict] | None:
    """
    Devuelve la lista de trenes cacheada para target_date, o None si todavía
    no existe (primer ciclo del día) o el objeto está corrupto. Nunca lanza
    excepción: el llamador decide si regenerarla desde GTFS.
    """
    try:
        response = s3.get_object(Bucket=bucket, Key=_key_for(target_date))
        body = json.loads(response["Body"].read())
        return body["trains"]
    except s3.exceptions.NoSuchKey:
        return None
    except (ClientError, ValueError, KeyError, TypeError) as exc:
        logger.warning(
            "Horario cacheado de %s en S3 no legible, se regenerará: %s",
            target_date.isoformat(), exc, extra=log_extra,
        )
        return None


def put_cached_schedule(s3, bucket: str, target_date: date, trains: list[dict], log_extra: dict) -> None:
    """
    Guarda el horario resuelto para target_date. No relanza errores de S3:
    un fallo aquí no invalida el horario ya resuelto en memoria para este
    ciclo, solo hace que el próximo ciclo vuelva a intentar descargarlo.
    """
    body = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trains": trains,
    }
    try:
        s3.put_object(
            Bucket=bucket,
            Key=_key_for(target_date),
            Body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(
            "Horario del día cacheado en s3://%s/%s (%d trenes)",
            bucket, _key_for(target_date), len(trains), extra=log_extra,
        )
    except ClientError as exc:
        logger.warning(
            "No se pudo cachear el horario del día en S3 (se reintentará el próximo ciclo): %s",
            exc, extra=log_extra,
        )
