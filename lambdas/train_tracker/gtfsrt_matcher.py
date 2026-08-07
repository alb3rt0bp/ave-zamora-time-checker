"""
gtfsrt_matcher.py
Empareja un tren (cod_comercial) con su entidad dentro del feed GTFS-RT
trip_updates_LD.json (ver gtfsrt_client.py) y extrae el stopTimeUpdate de la
parada solicitada.

Enriquecimiento aditivo y best-effort: nunca lanza excepción, y solo
devuelve datos cuando la coincidencia es inequívoca — nunca fabrica un
valor a partir de una coincidencia dudosa. Ver CLAUDE.md ("Additional
real-time source: GTFS-RT TripUpdates"): la regla de emparejamiento por
prefijo de tripId está validada contra un único ejemplo real observado
("0450512026-08-01" para el tren "04505"), así que se trata como
provisional hasta acumular más muestras.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import os

logger = logging.getLogger(f"train_tracker.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def find_stop_time_update(
    entities: list[dict], cod_comercial: str, station_code: str, log_extra: dict
) -> dict | None:
    """
    Busca, entre las entidades de trip_updates_LD.json, el trip cuyo tripId
    empiece por `cod_comercial`, y dentro de él, el stopTimeUpdate de
    `station_code`.

    Devuelve {"minutos_retraso": int, "hora_llegada": "HH:MM"} (con una,
    ambas, o ninguna clave, según lo que se haya podido extraer de forma
    fiable), o None si no hay una coincidencia inequívoca o no hay ningún
    dato utilizable.
    """
    if not cod_comercial:
        return None

    matches = [e for e in entities if _trip_id(e).startswith(cod_comercial)]

    if not matches:
        logger.debug("GTFS-RT: sin coincidencia de tripId para %s", cod_comercial, extra=log_extra)
        return None

    if len(matches) > 1:
        logger.warning(
            "GTFS-RT: %d coincidencias de tripId para %s (%s) — se descarta por ambigüedad",
            len(matches), cod_comercial, [_trip_id(m) for m in matches], extra=log_extra
        )
        return None

    stop_time_updates = matches[0].get("tripUpdate", {}).get("stopTimeUpdate", [])
    stop_update = next((s for s in stop_time_updates if s.get("stopId") == station_code), None)
    if stop_update is None:
        logger.debug(
            "GTFS-RT: trip de %s encontrado pero sin parada %s", cod_comercial, station_code,
            extra=log_extra
        )
        return None

    arrival = stop_update.get("arrival") or {}
    result = {}

    delay_seconds = arrival.get("delay")
    if delay_seconds is not None:
        try:
            # GTFS-RT expresa el retraso en SEGUNDOS; el resto del proyecto
            # (ultRetraso de flotaLD.json) lo usa en MINUTOS.
            result["minutos_retraso"] = round(float(delay_seconds) / 60)
        except (TypeError, ValueError):
            logger.warning(
                "GTFS-RT: delay no numérico '%s' para %s en %s", delay_seconds, cod_comercial,
                station_code, extra=log_extra
            )

    epoch = arrival.get("time")
    if epoch is not None:
        try:
            hora = datetime.fromtimestamp(int(epoch), tz=ZoneInfo("Europe/Madrid"))
            result["hora_llegada"] = hora.strftime("%H:%M")
        except (TypeError, ValueError):
            logger.warning(
                "GTFS-RT: epoch inválido '%s' para %s en %s", epoch, cod_comercial, station_code,
                extra=log_extra
            )

    # No fabricar un dict "vacío pero presente": ausencia de dato utilizable
    # equivale a no-match, igual que si nunca se hubiera encontrado la parada.
    return result or None


def _trip_id(entity: dict) -> str:
    return entity.get("tripUpdate", {}).get("trip", {}).get("tripId", "")
