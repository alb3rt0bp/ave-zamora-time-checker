"""
handler.py — Lambda: trend_fetcher

Ejecutada 2 veces al día (08:00 y 19:00, hora de Madrid) para consultar las
tendencias actuales de X en España vía xfetch.io y guardarlas en S3. Antes,
claude_client.py (tweet_notifier) consultaba xfetch.io una vez por cada tuit
redactado; consolidar la consulta a 2 veces al día reduce el consumo de
créditos de xfetch.io sin perder frescura relevante para el contenido de los
tuits. tweet_notifier lee el resultado desde S3 en vez de golpear xfetch.io
directamente — ver lambdas/tweet_notifier/trends_reader.py.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

import xfetch_client

logger = logging.getLogger("trend_fetcher")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

DATALAKE_S3_BUCKET = os.environ["DATALAKE_S3_BUCKET"]
TRENDS_S3_KEY = os.environ.get("TRENDS_S3_KEY", "trends/latest_hashtags.json")

s3 = boto3.client("s3")


def lambda_handler(event, context):
    """Consulta xfetch.io y guarda las tendencias actuales de X en S3."""
    log_extra = {"span_id": context.aws_request_id}

    hashtags = xfetch_client.get_trending_hashtags(log_extra)
    body = {
        "hashtags": hashtags,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    s3.put_object(
        Bucket=DATALAKE_S3_BUCKET,
        Key=TRENDS_S3_KEY,
        Body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info(
        "Tendencias guardadas en s3://%s/%s (%d hashtags)",
        DATALAKE_S3_BUCKET, TRENDS_S3_KEY, len(hashtags), extra=log_extra
    )
    return {"statusCode": 200, "hashtags_count": len(hashtags)}
