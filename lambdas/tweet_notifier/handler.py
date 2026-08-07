"""
handler.py — Lambda: tweet_notifier

Consume los eventos SNS publicados por train_tracker (ver
train_tracker/handler.py:_maybe_publish_delay_alert) cuando un tren se marca
entregado con más de DELAY_ALERT_THRESHOLD_MINUTES minutos de retraso (o es
el tren madrugador de Madrid, que siempre genera alerta), y redacta un tuit
para la Asociación de Usuarios de Trenes AVE de Zamora vía Claude
(claude_client.draft_tweet). Por ahora el tuit solo se loguea — la
publicación real en X (más abajo, comentada) queda pendiente de activar.

Las credenciales OAuth1.0a de la X Developer App se leen de Secrets Manager
y se cachean en memoria de módulo (por contenedor Lambda) tras la primera
lectura, para no golpear Secrets Manager en cada invocación.
"""

import json
import logging
import os

import boto3

import claude_client
from x_client import XClient

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

X_API_CREDENTIALS_SECRET_ARN = os.environ["X_API_CREDENTIALS_SECRET_ARN"]

secretsmanager = boto3.client("secretsmanager")

_credentials_cache: dict | None = None


def lambda_handler(event, context):
    """Punto de entrada: redacta y loguea un tuit por cada registro SNS del evento."""
    log_extra = {'span_id': context.aws_request_id}
    #credentials = _get_credentials(log_extra)
    #client = XClient(credentials, log_extra)

    published = 0
    for record in event.get("Records", []):
        alert = json.loads(record["Sns"]["Message"])
        cod_comercial = alert.get("cod_comercial")
        try:
            drafted = claude_client.draft_tweet(alert, log_extra)
        except Exception as exc:
            logger.error("Error redactando tuit para %s: %s", cod_comercial, exc, extra=log_extra)
            continue

        text = f"{drafted['tweet_text']}\n\n{' '.join(drafted['hashtags'])}"
        if len(text) > 280:
            logger.warning(
                "Tuit para %s supera los 280 caracteres (%d)",
                cod_comercial, len(text), extra=log_extra
            )
        logger.info(f'Texto que se va a publicar: {text}')
        #client.post_tweet(text)
        logger.info("Tuit publicado para el tren %s", cod_comercial, extra=log_extra)
        published += 1

    return {"statusCode": 200, "published": published}


def _get_credentials(log_extra: dict) -> dict:
    """
    Lee las credenciales OAuth1.0a desde Secrets Manager (consumer_key,
    consumer_secret, access_token, access_token_secret) y las cachea en el
    contenedor Lambda tras la primera lectura.
    """
    global _credentials_cache
    if _credentials_cache is None:
        resp = secretsmanager.get_secret_value(SecretId=X_API_CREDENTIALS_SECRET_ARN)
        _credentials_cache = json.loads(resp["SecretString"])
        logger.info("Credenciales de la API de X cargadas desde Secrets Manager", extra=log_extra)
    return _credentials_cache
