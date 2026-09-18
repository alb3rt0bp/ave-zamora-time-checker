"""
schedule_reference_cache.py
Cachea en S3 el horario de referencia (ver gtfs_schedule_reference.py) que
sirve /trains/schedule, con el mismo espíritu que
lambdas/train_tracker/schedule_cache.py: evita descargar y parsear el GTFS de
Renfe en cada petición del frontend, solo en la primera de cada día.

Prefijo distinto (schedules/reference-) del que usa train_tracker
(schedules/{fecha}.json): ese objeto tiene una forma distinta (solo los
trenes activos EN esa fecha concreta, con las excepciones de
calendar_dates.txt ya aplicadas), mientras que este es el patrón semanal
típico completo (incluye sábado/domingo aunque hoy sea lunes) — no se pueden
compartir sin ambigüedad.
"""

import json
import logging
import os
from datetime import date, datetime, timezone

from botocore.exceptions import ClientError

logger = logging.getLogger(f"api.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

SCHEDULE_REFERENCE_S3_PREFIX = os.environ.get("SCHEDULE_REFERENCE_S3_PREFIX", "schedules/reference-")


def _key_for(reference_date: date) -> str:
    return f"{SCHEDULE_REFERENCE_S3_PREFIX}{reference_date.isoformat()}.json"


def get_cached_reference(s3, bucket: str, reference_date: date, log_extra: dict) -> list[dict] | None:
    """
    Devuelve el horario de referencia cacheado para reference_date, o None si
    todavía no existe (primera petición del día) o el objeto está corrupto.
    Nunca lanza excepción: el llamador decide si regenerarlo desde GTFS.
    """
    try:
        response = s3.get_object(Bucket=bucket, Key=_key_for(reference_date))
        body = json.loads(response["Body"].read())
        return body["trains"]
    except s3.exceptions.NoSuchKey:
        return None
    except (ClientError, ValueError, KeyError, TypeError) as exc:
        logger.warning(
            "Horario de referencia cacheado de %s en S3 no legible, se regenerará: %s",
            reference_date.isoformat(), exc, extra=log_extra,
        )
        return None


def put_cached_reference(s3, bucket: str, reference_date: date, trains: list[dict], log_extra: dict) -> None:
    """
    Guarda el horario de referencia resuelto. No relanza errores de S3: un
    fallo aquí no invalida el horario ya resuelto en memoria para esta
    petición, solo hace que la próxima vuelva a intentar cachearlo.
    """
    body = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trains": trains,
    }
    try:
        s3.put_object(
            Bucket=bucket,
            Key=_key_for(reference_date),
            Body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(
            "Horario de referencia cacheado en s3://%s/%s (%d trenes)",
            bucket, _key_for(reference_date), len(trains), extra=log_extra,
        )
    except ClientError as exc:
        logger.warning(
            "No se pudo cachear el horario de referencia en S3 (se reintentará en la próxima petición): %s",
            exc, extra=log_extra,
        )
