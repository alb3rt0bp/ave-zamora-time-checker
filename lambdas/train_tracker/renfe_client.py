"""
renfe_client.py
Cliente HTTP para los endpoints de Renfe en tiempo real.
Incluye caché en memoria para evitar llamadas duplicadas en la misma ejecución.
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

FLOTA_URL         = "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json"
TRENES_ESTACIONES = "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/trenesConEstacionesLD.json"

# Tiempo de caché: no tiene sentido llamar más de una vez por minuto
CACHE_TTL_SECONDS = 60


class RenfeClient:
    def __init__(self, timeout_seconds: int = 15):
        self.timeout = timeout_seconds
        self._flota_cache: Optional[list] = None
        self._flota_cache_time: Optional[datetime] = None

    def get_flota(self) -> list[dict]:
        """
        Descarga flotaLD.json y devuelve la lista de trenes activos.
        
        Estructura esperada de cada elemento (campos relevantes):
        {
          "codComercial": "04154",
          "idTren": "12345",
          "codEstAnt": "71801",   ← código de la última estación
          "ultRetraso": 5,        ← minutos de retraso acumulado
          "lat": 41.5034,
          "lon": -5.7447,
          ...
        }
        """
        now = datetime.now(timezone.utc)

        # Devolver caché si es reciente
        if (
            self._flota_cache is not None
            and self._flota_cache_time is not None
            and (now - self._flota_cache_time).total_seconds() < CACHE_TTL_SECONDS
        ):
            logger.debug("Usando caché de flota (%d trenes)", len(self._flota_cache))
            return self._flota_cache

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

        logger.debug("flotaLD.json: %d trenes activos", len(trains))
        self._flota_cache = trains
        self._flota_cache_time = now
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
            logger.error("HTTP %d al acceder a %s", exc.code, url)
            raise
        except urllib.error.URLError as exc:
            logger.error("Error de red accediendo a %s: %s", url, exc.reason)
            raise
