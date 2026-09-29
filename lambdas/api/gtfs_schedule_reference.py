"""
gtfs_schedule_reference.py
Resuelve, a partir del GTFS estático de Renfe (ver gtfs_client.py), el
horario de REFERENCIA que sirve /trains/schedule: qué días de la semana
circula cada tren y a qué hora — el mismo shape que devuelve
handler._build_train_schedule_index(config/train_schedules.json).

Este módulo SÍ necesita calendar_dates.txt para resolver el patrón semanal
real — a diferencia de lo que decía una versión anterior de este docstring.
Verificado contra el feed real de Renfe (2026-09): `service_id` es en la
práctica un intervalo de validez de ~3-4 semanas codificado en su propio
nombre (p. ej. `2026-09-232026-10-14045051` = vigente 2026-09-23..10-14 para
el trip_short_name 045051), y dentro de ese intervalo `calendar.txt` casi
siempre marca el servicio activo TODOS los días de la semana — un valor
señuelo. El patrón real (p. ej. "circula solo los domingos") vive entero en
`calendar_dates.txt`, que dentro de ese mismo intervalo va retirando
(`exception_type=2`) casi todas las fechas y deja activas únicamente las que
el tren circula de verdad. Ignorar calendar_dates.txt (como hacía la versión
anterior) hace que CUALQUIER servicio con este patrón — que resultó ser
prácticamente todos — se resuelva como "circula los 7 días de la semana".

Por eso `_parse_calendar_weekdays` expande día a día el intervalo
start_date..end_date de la fila de calendar.txt vigente en reference_date
(aplicando su patrón semanal como valor por defecto) y superpone encima las
excepciones de calendar_dates.txt de ese mismo service_id, exactamente igual
que build_todays_trains hace para una fecha concreta — pero acumulando el
conjunto de weekdays resultantes en vez de una única fecha. El intervalo de
cada service_id observado en el feed real es corto (semanas, no meses), así
que este bucle día a día es barato incluso sumado sobre todos los trenes que
pasan por Zamora.

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
from datetime import date, datetime, timedelta

logger = logging.getLogger(f"api.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_CALENDAR_WEEKDAY_COLUMNS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)

_ADDED = "1"
_REMOVED = "2"


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
    GtfsClient.download_and_extract() (necesita trips.txt, stop_times.txt,
    calendar.txt Y calendar_dates.txt — ver docstring del módulo sobre por
    qué esta última ya no es opcional).

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
    weekdays_by_service = _parse_calendar_weekdays(
        gtfs_files["calendar.txt"], gtfs_files["calendar_dates.txt"], service_ids, reference_date
    )

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
    calendar_csv: str, calendar_dates_csv: str, service_ids: set, reference_date: date
) -> dict[str, list[int]]:
    """
    Para cada service_id de interés vigente en reference_date (start_date <=
    reference_date <= end_date), expande día a día su intervalo
    start_date..end_date — aplicando el patrón semanal de calendar.txt como
    valor por defecto y las excepciones de calendar_dates.txt de ese mismo
    service_id por encima (idéntico criterio que
    gtfs_schedule_builder._is_service_active, pero para cada fecha del
    intervalo en vez de una sola) — y devuelve el conjunto de weekdays
    (0=lunes..6=domingo) en los que el servicio queda realmente activo.

    Necesario porque en el feed real de Renfe calendar.txt marca casi todos
    los servicios activos los 7 días de la semana (ver docstring del
    módulo): el patrón real solo emerge tras aplicar calendar_dates.txt. Un
    service_id sin fila vigente, o cuyas fechas activas no caen en ningún
    día de la semana (no debería ocurrir, pero no se asume), queda fuera.
    """
    target_str = reference_date.strftime("%Y%m%d")

    valid_rows: dict[str, dict] = {}
    for row in _read_csv_rows(calendar_csv):
        service_id = row.get("service_id", "")
        if service_id not in service_ids:
            continue

        start_date = row.get("start_date", "")
        end_date = row.get("end_date", "")
        if not (start_date <= target_str <= end_date):
            continue

        valid_rows[service_id] = row

    if not valid_rows:
        return {}

    exceptions_by_service: dict[str, dict[str, str]] = {service_id: {} for service_id in valid_rows}
    for row in _read_csv_rows(calendar_dates_csv):
        service_id = row.get("service_id", "")
        if service_id not in exceptions_by_service:
            continue
        exceptions_by_service[service_id][row.get("date", "")] = row.get("exception_type", "")

    weekdays_by_service: dict[str, list[int]] = {}
    for service_id, row in valid_rows.items():
        start = datetime.strptime(row["start_date"], "%Y%m%d").date()
        end = datetime.strptime(row["end_date"], "%Y%m%d").date()
        exceptions = exceptions_by_service[service_id]

        active_weekdays = set()
        current = start
        while current <= end:
            exception_type = exceptions.get(current.strftime("%Y%m%d"))
            if exception_type == _REMOVED:
                active = False
            elif exception_type == _ADDED:
                active = True
            else:
                active = row.get(_CALENDAR_WEEKDAY_COLUMNS[current.weekday()], "0") == "1"

            if active:
                active_weekdays.add(current.weekday())
            current += timedelta(days=1)

        if active_weekdays:
            weekdays_by_service[service_id] = sorted(active_weekdays)

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
