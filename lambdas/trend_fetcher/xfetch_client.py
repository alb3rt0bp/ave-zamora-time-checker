"""
xfetch_client.py
Cliente mínimo para el endpoint de tendencias de xfetch.io (proveedor
externo de datos públicos de X/Twitter — no es la API oficial de X ni de
Anthropic: https://xfetch.io/docs) usado por handler.py (lambda
trend_fetcher) para consultar las tendencias actuales 2 veces al día y
guardarlas en S3 — ver lambdas/tweet_notifier/trends_reader.py, que las lee
de ahí en vez de golpear xfetch.io en cada tuit. Implementado solo con
librería estándar (urllib), igual que renfe_client.py/x_client.py.

Las credenciales OAuth1.0a de X (tweet_notifier/x_client.py) son un tema
aparte: xfetch.io requiere su propia API key, gestionada en su propio
dashboard.
"""

import json
import logging
import os
import urllib.error
import urllib.request

import boto3

logger = logging.getLogger(f"tweet_notifier.{__name__}")

TRENDS_URL = "https://api.xfetch.io/v1/trends"
SPAIN_WOEID = os.environ.get("XFETCH_TRENDS_WOEID", "23424950")
XFETCH_API_KEY_SECRET_ARN = os.environ.get("XFETCH_API_KEY_SECRET_ARN", "")

secretsmanager = boto3.client("secretsmanager")

_api_key_cache: str | None = None


def _get_api_key(log_extra: dict) -> str:
    """Lee la API key de xfetch.io desde Secrets Manager y la cachea en el contenedor Lambda."""
    global _api_key_cache
    if _api_key_cache is None:
        resp = secretsmanager.get_secret_value(SecretId=XFETCH_API_KEY_SECRET_ARN)
        _api_key_cache = resp["SecretString"]
        logger.info("API key de xfetch.io cargada desde Secrets Manager", extra=log_extra)
    return _api_key_cache


def get_trending_hashtags(log_extra: dict, limit: int = 50, timeout_seconds: int = 5) -> list[str]:
    """
    Devuelve los nombres de tendencia actuales en España que son hashtags
    (empiezan por '#'; xfetch también devuelve tendencias sin hashtag).
    Nunca lanza excepción: es un enriquecimiento opcional, así que cualquier
    fallo (red, auth, JSON, forma de respuesta inesperada) se loguea como
    aviso y devuelve lista vacía en vez de bloquear la redacción del tuit.
    """
    try:
        api_key = _get_api_key(log_extra)
        url = f"{TRENDS_URL}?woeid={SPAIN_WOEID}&limit={limit}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            body = json.loads(response.read())
        logger.info(f'xFetch credits remaining: {body["meta"]["credits"]["remaining"]}')
        return [
            item["trend_name"] for item in body.get("data", [])
            if item.get("trend_name", "").startswith("#")
        ]
    except (urllib.error.URLError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Error consultando tendencias en xfetch.io: %s", exc, extra=log_extra)
        return []
