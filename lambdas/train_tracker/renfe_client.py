"""
renfe_client.py
Cliente HTTP para los endpoints de Renfe en tiempo real.
"""

import json
import logging
import urllib.request
import urllib.error
import os

logger = logging.getLogger(f"train_tracker.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

FLOTA_URL         = "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json"
TRENES_ESTACIONES = "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/trenesConEstacionesLD.json"


class RenfeClient:
    def __init__(self, log_extra, timeout_seconds: int = 15):
        self.timeout = timeout_seconds
        self.log_extra = log_extra

    def get_flota(self) -> list[dict]:
        """
        Descarga flotaLD.json y devuelve la lista de trenes activos.

        Estructura esperada de cada elemento (campos relevantes):
        {
          "codComercial": "04154",
          "idTren": "12345",
          "codEstAnt": "30200",   ← código de la última estación
          "ultRetraso": 5,        ← minutos de retraso acumulado
          "lat": 41.5034,
          "lon": -5.7447,
          ...
        }
        """
        raw = self._fetch(FLOTA_URL)
        data = json.loads(raw)

        # La API puede devolver la lista directamente o dentro de una clave
        if isinstance(data, list):
            trains = data
        elif isinstance(data, dict):
            # Intentar claves comunes
            trains = (
                data.get("trenes")
                or []
            )
        else:
            trains = []

        logger.debug("flotaLD.json: %d trenes activos", len(trains), extra=self.log_extra)
        return trains

    def get_trenes_con_estaciones(self) -> list[dict]:
        """
        Descarga trenesConEstacionesLD.json.
        Útil para obtener el itinerario completo de un tren y
        la hora planificada de paso por cada estación.
        """
        raw = self._fetch(TRENES_ESTACIONES)
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("trenes") or data.get("data") or []
        return []

    def _fetch(self, url: str) -> bytes:
        """Realiza la petición HTTP con timeout y User-Agent adecuado."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "TrainObservability/1.0 (AWS Lambda)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            logger.error("HTTP %d al acceder a %s", exc.code, url, extra=self.log_extra)
            raise
        except urllib.error.URLError as exc:
            logger.error("Error de red accediendo a %s: %s", url, exc.reason, extra=self.log_extra)
            raise
