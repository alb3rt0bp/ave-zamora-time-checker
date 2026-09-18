"""
gtfs_client.py
Cliente para el feed GTFS estático de AV/Larga Distancia de Renfe
(https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip). Descarga
el zip completo (~700 KB, ~90k filas en total entre los 6 CSV que contiene)
y devuelve su contenido en memoria — sin escritura a disco ni caching aquí.
gtfs_schedule_builder.py se encarga de parsear ese contenido; ver handler.py
para el cacheo diario en S3 del horario ya resuelto (evita repetir esta
descarga en cada uno de los ~180 ciclos de polling del día).
"""

import io
import logging
import os
import urllib.error
import urllib.request
import zipfile

logger = logging.getLogger(f"train_tracker.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

GTFS_ZIP_URL = os.environ.get(
    "GTFS_ZIP_URL", "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip"
)

# Ficheros que gtfs_schedule_builder.py necesita; stops.txt/routes.txt/
# agency.txt no hacen falta para resolver horarios de paso por Zamora.
REQUIRED_FILES = ("trips.txt", "stop_times.txt", "calendar.txt", "calendar_dates.txt")


class GtfsClient:
    def __init__(self, log_extra, timeout_seconds: int = 30):
        self.timeout = timeout_seconds
        self.log_extra = log_extra

    def download_and_extract(self) -> dict[str, str]:
        """
        Descarga GTFS_ZIP_URL y devuelve {nombre_fichero: contenido_texto} para
        cada uno de REQUIRED_FILES. Lanza FileNotFoundError si el zip no
        contiene alguno de ellos (formato inesperado de Renfe) — el llamador
        decide cómo degradar (ver handler.py).

        Las filas de estos ficheros vienen rellenadas con espacios de cola
        hasta un ancho fijo (observado en el feed real de Renfe); no se
        recorta aquí porque csv.DictReader necesita el texto completo tal
        cual — gtfs_schedule_builder.py hace el .strip() campo a campo.
        """
        raw = self._fetch(GTFS_ZIP_URL)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
            missing = [f for f in REQUIRED_FILES if f not in names]
            if missing:
                raise FileNotFoundError(
                    f"El GTFS descargado no contiene: {', '.join(missing)}"
                )
            files = {name: zf.read(name).decode("utf-8-sig") for name in REQUIRED_FILES}

        logger.info(
            "GTFS descargado y extraído: %d ficheros, %d bytes totales",
            len(files), sum(len(v) for v in files.values()), extra=self.log_extra,
        )
        return files

    def _fetch(self, url: str) -> bytes:
        """Realiza la petición HTTP con timeout y User-Agent adecuado."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "TrainObservability/1.0 (AWS Lambda)",
                "Accept": "application/zip",
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
