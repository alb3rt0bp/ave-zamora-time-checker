"""
gtfsrt_client.py
Cliente HTTP para el feed GTFS-Realtime de Larga/Media Distancia de Renfe
(https://gtfsrt.renfe.com/trip_updates_LD.json), listado a través del Punto
de Acceso Nacional de transporte (nap.transportes.gob.es, dataset 897) más
que en el propio portal data.renfe.com. Da el retraso por parada calculado
por Renfe, más preciso que inferirlo de ultRetraso + codEstAnt en flotaLD.json.

Ver CLAUDE.md ("Additional real-time source: GTFS-RT TripUpdates") para el
contexto completo. Se usa como enriquecimiento aditivo, no como sustituto de
RenfeClient.
"""

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates_LD.json"


class GtfsRtClient:
    def __init__(self, log_extra, timeout_seconds: int = 10):
        self.timeout = timeout_seconds
        self.log_extra = log_extra

    def get_trip_updates(self) -> list[dict]:
        """
        Descarga trip_updates_LD.json y devuelve la lista `entity`.

        Estructura esperada (GTFS-Realtime v2.0, campos relevantes):
        {
          "header": {"gtfsRealtimeVersion": "2.0", "timestamp": "..."},
          "entity": [
            {
              "id": "...",
              "tripUpdate": {
                "trip": {"tripId": "0450512026-08-01", "scheduleRelationship": "SCHEDULED"},
                "stopTimeUpdate": [
                  {"stopId": "30200", "arrival": {"time": "1785661800", "delay": 0}}
                ]
              }
            }
          ]
        }
        """
        raw = self._fetch(TRIP_UPDATES_URL)
        data = json.loads(raw)

        if isinstance(data, dict):
            entities = data.get("entity") or []
        else:
            entities = []

        logger.debug("trip_updates_LD.json: %d entidades", len(entities), extra=self.log_extra)
        return entities

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
