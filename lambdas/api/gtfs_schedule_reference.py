"""
gtfs_schedule_reference.py
Resuelve, a partir del GTFS estático de Renfe (ver gtfs_client.py), el
horario de REFERENCIA que sirve /trains/schedule: qué días de la semana
circula cada tren y a qué hora — el mismo shape que devuelve
handler._build_train_schedule_index(config/train_schedules.json).

A diferencia de lambdas/train_tracker/gtfs_schedule_builder.py
(build_todays_trains), que resuelve los trenes activos en UNA fecha
concreta aplicando las excepciones puntuales de calendar_dates.txt, este
módulo deriva el patrón SEMANAL típico de cada tren a partir únicamente del
patrón de calendar.txt vigente en reference_date — ignorando a propósito
calendar_dates.txt: sus excepciones son ajustes puntuales para un día
concreto (festivos, refuerzos), no reflejan qué días circula un tren
"normalmente", que es lo que esta pantalla de referencia quiere mostrar.

Se duplican aquí (en vez de importarse de gtfs_schedule_builder.py) los
mismos helpers de parseo de CSV, porque cada Lambda de este proyecto empaqueta
su propio código de forma independiente (CodeUri por función en
infrastructure/template.yaml, sin capa compartida) — mismo motivo por el que
x_client.py/renfe_client.py implementan su propio cliente HTTP en vez de
compartir uno.
"""

import csv
import io
import logging
import os
from datetime import date

logger = logging.getLogger(f"api.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_CALENDAR_WEEKDAY_COLUMNS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)


def _read_csv_rows(csv_text: str):
    """
    csv.DictReader normal, pero recortando espacios en claves Y valores — el
    feed real de Renfe rellena cada fila (cabecera incluida) con espacios de
    cola hasta un ancho fijo. Mismo patrón que gtfs_schedule_builder.py.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        yield {k.strip(): (v or "").strip() for k, v in row.items()}


def build_schedule_reference(
    gtfs_files: dict[str, str],
    reference_date: date,
    zamora_code: str,
    chamartin_code: str,
    log_extra: dict,
) -> list[dict]:
    """
    gtfs_files: dict {nombre_fichero: contenido_texto}, igual que devuelve
    GtfsClient.download_and_extract() (aquí solo hacen falta trips.txt,
    stop_times.txt y calendar.txt — calendar_dates.txt no se usa, ver
    docstring del módulo).

    Devuelve una lista de dicts {cod_comercial, sentido, hora_salida,
    hora_llegada_destino, weekdays}, ordenada por cod_comercial — mismo
    shape que TrainSchedule en el frontend (frontend/src/types.ts) y que
    handler._build_train_schedule_index.
    """
    zamora_by_trip, chamartin_by_trip = _index_stop_times(
        gtfs_files["stop_times.txt"], zamora_code, chamartin_code
    )
    candidate_trip_ids = set(zamora_by_trip) & set(chamartin_by_trip)

    trips = _index_trips(gtfs_files["trips.txt"], candidate_trip_ids, log_extra)

    service_ids = {info["service_id"] for info in trips.values()}
    weekdays_by_service = _parse_calendar_weekdays(gtfs_files["calendar.txt"], service_ids, reference_date)

    entries: dict[tuple, dict] = {}
    for trip_id, trip_info in trips.items():
        weekdays = weekdays_by_service.get(trip_info["service_id"])
        if not weekdays:
            continue

        sentido = _infer_sentido(zamora_by_trip[trip_id], chamartin_by_trip[trip_id], trip_id, log_extra)
        if sentido is None:
            continue

        if sentido == "Madrid":
            hora_salida = zamora_by_trip[trip_id]["departure_time"]
            hora_llegada_destino = chamartin_by_trip[trip_id]["arrival_time"]
        else:
            hora_salida = chamartin_by_trip[trip_id]["departure_time"]
            hora_llegada_destino = zamora_by_trip[trip_id]["arrival_time"]

        # Dedup: dos trip_id distintos (composición doble) pueden coincidir
        # en cod_comercial/sentido/horas — es el mismo tren a estos efectos,
        # mismo criterio que build_todays_trains.
        key = (trip_info["cod_comercial"], sentido, hora_salida, hora_llegada_destino)
        entry = entries.setdefault(key, {
            "cod_comercial": trip_info["cod_comercial"],
            "sentido": sentido,
            "hora_salida": hora_salida,
            "hora_llegada_destino": hora_llegada_destino,
            "weekdays": set(),
        })
        entry["weekdays"].update(weekdays)

    result = [{**entry, "weekdays": sorted(entry["weekdays"])} for entry in entries.values()]
    return sorted(result, key=lambda t: t["cod_comercial"])


def _index_stop_times(
    stop_times_csv: str, zamora_code: str, chamartin_code: str
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Idéntico a gtfs_schedule_builder._index_stop_times."""
    zamora_by_trip: dict[str, dict] = {}
    chamartin_by_trip: dict[str, dict] = {}

    for row in _read_csv_rows(stop_times_csv):
        stop_id = row.get("stop_id", "")
        if stop_id not in (zamora_code, chamartin_code):
            continue

        trip_id = row.get("trip_id", "")
        entry = {
            "stop_sequence": int(row.get("stop_sequence") or "0"),
            "arrival_time": _normalize_time(row.get("arrival_time", "")),
            "departure_time": _normalize_time(row.get("departure_time", "")),
        }
        if stop_id == zamora_code:
            zamora_by_trip[trip_id] = entry
        else:
            chamartin_by_trip[trip_id] = entry

    return zamora_by_trip, chamartin_by_trip


def _index_trips(trips_csv: str, candidate_trip_ids: set, log_extra: dict) -> dict[str, dict]:
    """Idéntico a gtfs_schedule_builder._index_trips."""
    trips: dict[str, dict] = {}

    for row in _read_csv_rows(trips_csv):
        trip_id = row.get("trip_id", "")
        if trip_id not in candidate_trip_ids:
            continue

        cod_comercial = row.get("trip_short_name", "")
        if not cod_comercial:
            logger.warning(
                "GTFS: trip_id %s pasa por Zamora y Chamartín pero no tiene "
                "trip_short_name — se descarta (sin cod_comercial que asignar)",
                trip_id, extra=log_extra,
            )
            continue

        trips[trip_id] = {
            "cod_comercial": cod_comercial,
            "service_id": row.get("service_id", ""),
        }

    return trips


def _parse_calendar_weekdays(
    calendar_csv: str, service_ids: set, reference_date: date
) -> dict[str, list[int]]:
    """
    Para cada service_id de interés vigente en reference_date (start_date <=
    reference_date <= end_date), devuelve la lista de weekdays (0=lunes..
    6=domingo) en los que circula según su patrón semanal — sin mirar
    calendar_dates.txt, ver docstring del módulo. Un service_id sin fila
    vigente (superada o aún no vigente) o sin ningún día activo queda fuera.
    """
    target_str = reference_date.strftime("%Y%m%d")

    weekdays_by_service: dict[str, list[int]] = {}
    for row in _read_csv_rows(calendar_csv):
        service_id = row.get("service_id", "")
        if service_id not in service_ids:
            continue

        start_date = row.get("start_date", "")
        end_date = row.get("end_date", "")
        if not (start_date <= target_str <= end_date):
            continue

        active = [i for i, col in enumerate(_CALENDAR_WEEKDAY_COLUMNS) if row.get(col, "0") == "1"]
        if active:
            weekdays_by_service[service_id] = active

    return weekdays_by_service


def _infer_sentido(zamora_stop: dict, chamartin_stop: dict, trip_id: str, log_extra: dict) -> str | None:
    """Idéntico a gtfs_schedule_builder._infer_sentido."""
    if chamartin_stop["stop_sequence"] > zamora_stop["stop_sequence"]:
        return "Madrid"
    if chamartin_stop["stop_sequence"] < zamora_stop["stop_sequence"]:
        return "Galicia"

    logger.warning(
        "GTFS: trip_id %s tiene a Zamora y Chamartín con el mismo stop_sequence "
        "— no se puede inferir el sentido, se descarta", trip_id, extra=log_extra,
    )
    return None


def _normalize_time(raw: str) -> str:
    """Idéntico a gtfs_schedule_builder._normalize_time."""
    parts = raw.strip().split(":")
    hour = int(parts[0]) % 24
    minute = int(parts[1])
    return f"{hour:02d}:{minute:02d}"
