"""
trends_reader.py
Lee las tendencias de X en España guardadas en S3 por la lambda
trend_fetcher (ver lambdas/trend_fetcher/handler.py), que las consulta en
xfetch.io 2 veces al día (08:00 y 19:00, hora de Madrid) en vez de una vez
por tuit — reduce el consumo de créditos de xfetch.io sin perder frescura
relevante. Mismo espíritu que el resto de enriquecimientos aditivos de este
proyecto (p. ej. GTFS-RT en train_tracker): si el fichero no existe, está
corrupto o es demasiado antiguo (posible fallo de trend_fetcher), se loguea
un aviso y se sigue redactando el tuit sin hashtag de tendencia.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(f"tweet_notifier.{__name__}")

DATALAKE_S3_BUCKET = os.environ.get("DATALAKE_S3_BUCKET", "")
TRENDS_S3_KEY = os.environ.get("TRENDS_S3_KEY", "trends/latest_hashtags.json")
# Cubre con margen un ciclo de trend_fetcher fallido (schedule cada ~11-13h)
# sin descartar tendencias todavía útiles.
TRENDS_MAX_AGE_HOURS = int(os.environ.get("TRENDS_MAX_AGE_HOURS", "24"))

s3 = boto3.client("s3")


def get_trending_hashtags(log_extra: dict) -> list[str]:
    """
    Devuelve los hashtags de tendencia guardados en S3 por trend_fetcher.
    Nunca lanza excepción: es un enriquecimiento opcional, así que cualquier
    fallo (S3, JSON, fichero ausente o caducado) se loguea como aviso y
    devuelve lista vacía en vez de bloquear la redacción del tuit.
    """
    try:
        response = s3.get_object(Bucket=DATALAKE_S3_BUCKET, Key=TRENDS_S3_KEY)
        body = json.loads(response["Body"].read())
        fetched_at = datetime.fromisoformat(body["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours > TRENDS_MAX_AGE_HOURS:
            logger.warning(
                "Tendencias en S3 caducadas (%.1fh, límite %dh); se ignoran",
                age_hours, TRENDS_MAX_AGE_HOURS, extra=log_extra
            )
            return []
        return body["hashtags"]
    except (ClientError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Error leyendo tendencias desde S3: %s", exc, extra=log_extra)
        return []
