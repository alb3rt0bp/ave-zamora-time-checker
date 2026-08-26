"""
gtfs_schedule_builder.py
Resuelve, a partir del contenido crudo de un GTFS estático (ver
gtfs_client.py), la lista de trenes que pasan por Zamora en una fecha
concreta — mismo shape que las entradas de config/train_schedules.json, para
poder sustituir esa fuente estática sin tocar schedule_matcher.py ni el resto
del pipeline.

Hallazgos del feed real de Renfe (AV/Larga Distancia) en los que se apoya
este módulo, verificados manualmente contra ssl.renfe.com/gtransit/
Fichero_AV_LD/google_transit.zip en agosto de 2026:

- `stops.txt` usa los mismos códigos Adif que ya usa este proyecto para
  `codEstAnt`/`codEstSig` (30200=Zamora, 17000=Chamartín) — sin tabla de
  mapeo intermedia.
- `trips.txt.trip_short_name` es directamente el `cod_comercial` (p. ej.
  "04154"). Esto también confirma la regla de emparejamiento por prefijo de
  `gtfsrt_matcher.py` para el feed en tiempo real: mismo `trip_id` con la
  misma convención en ambos feeds.
- El sentido se infiere sin ambigüedad comparando `stop_sequence` de Zamora
  y Chamartín dentro del mismo trip: si Chamartín va DESPUÉS de Zamora, el
  tren circula hacia Madrid; si va ANTES, hacia Galicia.
- `calendar.txt` casi siempre viene "activo todos los días de la semana"
  dentro de un rango de fechas, y es `calendar_dates.txt` quien define el
  patrón real mediante excepciones (exception_type 1=añadir ese día pese al
  calendario, 2=quitarlo) — no es un patrón semanal fijo para siempre, por
  lo que hay que resolver la fecha exacta, no solo el día de la semana.
"""

import csv
import io
import logging
import os
from datetime import date

logger = logging.getLogger(f"train_tracker.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TIPO_DIA_WEEKDAYS = {
    "laborable": [0, 1, 2, 3, 4],
    "sabado": [5],
    "domingo": [6],
}

_ADDED = "1"
_REMOVED = "2"


def _read_csv_rows(csv_text: str):
    """
    csv.DictReader normal, pero recortando espacios en claves Y valores. El
    feed real de Renfe rellena cada fila (cabecera incluida) con espacios de
    cola hasta un ancho fijo: sin este recorte, la clave de la ÚLTIMA columna
    de la cabecera queda corrupta (p. ej. "end_date" + espacios), así que
    cualquier row.get("end_date") caería siempre al valor por defecto. Mismo
    patrón que ya usa scripts/compile_schedules.py para los CSV de origen.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        yield {k.strip(): (v or "").strip() for k, v in row.items()}


# Orden de columnas de calendar.txt == orden de datetime.date.weekday()
# (0=lunes ... 6=domingo) en ambos casos, así que se puede indexar directo.
_CALENDAR_WEEKDAY_COLUMNS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)


def build_todays_trains(
    gtfs_files: dict[str, str],
    target_date: date,
    zamora_code: str,
    chamartin_code: str,
    log_extra: dict,
) -> list[dict]:
    """
    gtfs_files: dict {nombre_fichero: contenido_texto} tal y como lo devuelve
    GtfsClient.download_and_extract() (trips.txt, stop_times.txt,
    calendar.txt, calendar_dates.txt).

    Devuelve una lista de dicts con el mismo shape que
    config/train_schedules.json: cod_comercial, sentido, tipo_dia, weekdays,
    hora_salida, hora_llegada_destino. Ordenada de forma determinista por
    (sentido, hora_salida).
    """
    zamora_by_trip, chamartin_by_trip = _index_stop_times(
        gtfs_files["stop_times.txt"], zamora_code, chamartin_code
    )
    candidate_trip_ids = set(zamora_by_trip) & set(chamartin_by_trip)

    trips = _index_trips(gtfs_files["trips.txt"], candidate_trip_ids, log_extra)

    service_ids = {info["service_id"] for info in trips.values()}
    calendar_defaults = _parse_calendar(gtfs_files["calendar.txt"], service_ids, target_date)
    exceptions = _parse_calendar_dates(gtfs_files["calendar_dates.txt"], service_ids, target_date)

    tipo_dia = _tipo_dia_for(target_date)
    weekdays = TIPO_DIA_WEEKDAYS[tipo_dia]

    entries = {}
    for trip_id, trip_info in trips.items():
        if not _is_service_active(trip_info["service_id"], calendar_defaults, exceptions):
            continue

        sentido = _infer_sentido(
            zamora_by_trip[trip_id], chamartin_by_trip[trip_id], trip_id, log_extra
        )
        if sentido is None:
            continue

        if sentido == "Madrid":
            hora_salida = zamora_by_trip[trip_id]["departure_time"]
            hora_llegada_destino = chamartin_by_trip[trip_id]["arrival_time"]
        else:
            hora_salida = chamartin_by_trip[trip_id]["departure_time"]
            hora_llegada_destino = zamora_by_trip[trip_id]["arrival_time"]

        # Dedup: dos trip_id distintos (p. ej. composición doble con dos
        # orígenes) pueden coincidir en cod_comercial/sentido/horas en Zamora
        # y Chamartín — es el mismo tren a efectos de este sistema.
        key = (trip_info["cod_comercial"], sentido, hora_salida, hora_llegada_destino)
        entries[key] = {
            "cod_comercial": trip_info["cod_comercial"],
            "sentido": sentido,
            "tipo_dia": tipo_dia,
            "weekdays": weekdays,
            "hora_salida": hora_salida,
            "hora_llegada_destino": hora_llegada_destino,
        }

    return sorted(entries.values(), key=lambda t: (t["sentido"], t["hora_salida"]))


def _index_stop_times(
    stop_times_csv: str, zamora_code: str, chamartin_code: str
) -> tuple[dict[str, dict], dict[str, dict]]:
    """
    Un único paso por stop_times.txt: para cada trip_id que pare en Zamora
    y/o Chamartín, guarda su stop_sequence (como int, para poder comparar
    orden) y sus horas de llegada/salida normalizadas a "HH:MM".
    """
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
    """
    Un único paso por trips.txt, filtrando a los trip_id candidatos (los que
    ya sabemos que paran en Zamora y Chamartín). Descarta filas sin
    trip_short_name: sin él no hay cod_comercial que asignar.
    """
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


def _parse_calendar(
    calendar_csv: str, service_ids: set, target_date: date
) -> dict[str, bool]:
    """
    Para cada service_id de interés, resuelve si está activo por defecto en
    target_date según su patrón semanal y su rango start_date/end_date — sin
    tener en cuenta todavía las excepciones de calendar_dates.txt. Un
    service_id que no aparezca en calendar.txt (servicio definido solo por
    excepciones, permitido por el estándar GTFS) queda ausente del dict; se
    trata como inactivo por defecto en _is_service_active.
    """
    weekday_column = _CALENDAR_WEEKDAY_COLUMNS[target_date.weekday()]
    target_str = target_date.strftime("%Y%m%d")

    defaults: dict[str, bool] = {}
    for row in _read_csv_rows(calendar_csv):
        service_id = row.get("service_id", "")
        if service_id not in service_ids:
            continue

        start_date = row.get("start_date", "")
        end_date = row.get("end_date", "")
        in_range = start_date <= target_str <= end_date
        active_weekday = row.get(weekday_column, "0") == "1"
        defaults[service_id] = in_range and active_weekday

    return defaults


def _parse_calendar_dates(
    calendar_dates_csv: str, service_ids: set, target_date: date
) -> dict[str, bool]:
    """
    Para cada service_id de interés, busca una excepción puntual para
    target_date (exception_type 1=añadir, 2=quitar). Devuelve solo los
    service_id que tengan una excepción ese día concreto — su valor
    sobrescribe el default de _parse_calendar en _is_service_active.
    """
    target_str = target_date.strftime("%Y%m%d")

    exceptions: dict[str, bool] = {}
    for row in _read_csv_rows(calendar_dates_csv):
        service_id = row.get("service_id", "")
        if service_id not in service_ids:
            continue
        if row.get("date", "") != target_str:
            continue

        exceptions[service_id] = row.get("exception_type", "") == _ADDED

    return exceptions


def _is_service_active(
    service_id: str, calendar_defaults: dict[str, bool], exceptions: dict[str, bool]
) -> bool:
    if service_id in exceptions:
        return exceptions[service_id]
    return calendar_defaults.get(service_id, False)


def _infer_sentido(zamora_stop: dict, chamartin_stop: dict, trip_id: str, log_extra: dict) -> str | None:
    """
    Chamartín después de Zamora en la secuencia de paradas → tren hacia
    Madrid. Chamartín antes de Zamora → tren hacia Galicia. Devuelve None
    (con warning) si ambas paradas comparten stop_sequence, lo cual no
    debería ocurrir nunca en un itinerario válido.
    """
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
    """
    GTFS expresa las horas como "H:MM:SS" (a veces sin cero de relleno en la
    hora, y con horas >=24 para servicios que cruzan medianoche). Se
    normaliza a "HH:MM" igual que el resto del proyecto; el caso >=24h se
    envuelve al día siguiente con %, ya que este sistema no modela trayectos
    que cruzan la medianoche (mismo alcance que el resto del código).
    """
    parts = raw.strip().split(":")
    hour = int(parts[0]) % 24
    minute = int(parts[1])
    return f"{hour:02d}:{minute:02d}"


def _tipo_dia_for(target_date: date) -> str:
    weekday = target_date.weekday()
    if weekday in (0, 1, 2, 3, 4):
        return "laborable"
    elif weekday == 5:
        return "sabado"
    else:
        return "domingo"
