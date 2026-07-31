"""
x_client.py
Cliente mínimo para publicar tuits en la API v2 de X (Twitter) usando
OAuth 1.0a "user context". Implementado solo con librería estándar (sin
tweepy/requests_oauthlib), igual que renfe_client.py en train_tracker.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

TWEETS_URL = "https://api.x.com/2/tweets"


class XClient:
    def __init__(self, credentials: dict, log_extra: dict, timeout_seconds: int = 15):
        """
        credentials: dict con consumer_key, consumer_secret, access_token,
        access_token_secret — las 4 credenciales OAuth1.0a "Read and Write"
        de la X Developer App de la asociación.
        """
        self.credentials = credentials
        self.log_extra = log_extra
        self.timeout = timeout_seconds

    def post_tweet(self, text: str) -> dict:
        """Publica un tuit. Lanza excepción si la API devuelve error."""
        body = json.dumps({"text": text}).encode("utf-8")
        headers = {
            "Authorization": self._oauth1_header("POST", TWEETS_URL),
            "Content-Type": "application/json",
            "User-Agent": "ZamoraTrainObservability/1.0 (AWS Lambda)",
        }
        req = urllib.request.Request(TWEETS_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                logger.info("Tuit publicado correctamente", extra=self.log_extra)
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.error("Error HTTP %d publicando tuit: %s", exc.code, detail, extra=self.log_extra)
            raise
        except urllib.error.URLError as exc:
            logger.error("Error de red publicando tuit: %s", exc.reason, extra=self.log_extra)
            raise

    def _oauth1_header(self, method: str, url: str,
                        nonce: str | None = None, timestamp: str | None = None) -> str:
        """
        Construye la cabecera Authorization OAuth1.0a. El cuerpo va como
        JSON (no application/x-www-form-urlencoded), así que la firma solo
        cubre los parámetros oauth_* y de query string (ninguno aquí) — el
        body NO entra en la base string, según la propia spec de OAuth1.
        `nonce`/`timestamp` son inyectables para tests deterministas.
        """
        oauth_params = {
            "oauth_consumer_key": self.credentials["consumer_key"],
            "oauth_nonce": nonce or secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": timestamp or str(int(time.time())),
            "oauth_token": self.credentials["access_token"],
            "oauth_version": "1.0",
        }
        oauth_params["oauth_signature"] = self._sign(method, url, oauth_params)

        return "OAuth " + ", ".join(
            f'{self._percent_encode(k)}="{self._percent_encode(v)}"'
            for k, v in sorted(oauth_params.items())
        )

    def _sign(self, method: str, url: str, oauth_params: dict) -> str:
        param_string = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}"
            for k, v in sorted(oauth_params.items())
        )
        base_string = "&".join([
            method.upper(),
            self._percent_encode(url),
            self._percent_encode(param_string),
        ])
        signing_key = "&".join([
            self._percent_encode(self.credentials["consumer_secret"]),
            self._percent_encode(self.credentials["access_token_secret"]),
        ])
        digest = hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1).digest()
        return base64.b64encode(digest).decode("utf-8")

    @staticmethod
    def _percent_encode(value: str) -> str:
        return urllib.parse.quote(str(value), safe="")
