"""
Payloads de ejemplo que devolvería el feed GTFS-RT trip_updates_LD.json.

Los epoch usados corresponden al 2026-01-05 (MONDAY en reference_dates.py),
en horario de invierno (CET, UTC+1), elegidos a propósito para que una
conversión a UTC en vez de a Europe/Madrid dé una hora distinta y el test
falle de forma visible en vez de colar por casualidad:
  - 1767598440 → 08:34 hora de Madrid (07:34 UTC)
  - 1767600900 → 09:15 hora de Madrid (08:15 UTC)
"""

ZAMORA_EPOCH = 1767598440   # 08:34 Europe/Madrid
CHAMARTIN_EPOCH = 1767600900  # 09:15 Europe/Madrid

# Trip de M100 (Madrid): stopTimeUpdate tanto en Zamora como en Chamartín,
# para poder testear el "bonus" de hora_paso_zamora_gtfsrt en trenes Madrid.
ENTITY_M100 = {
    "id": "1",
    "tripUpdate": {
        "trip": {"tripId": "M10012026-01-05", "scheduleRelationship": "SCHEDULED"},
        "stopTimeUpdate": [
            {"stopId": "30200", "arrival": {"time": str(ZAMORA_EPOCH), "delay": 180}},
            {"stopId": "17000", "arrival": {"time": str(CHAMARTIN_EPOCH), "delay": 300}},
        ],
    },
}

# Trip de G100 (Galicia): solo Zamora, sin retraso.
ENTITY_G100 = {
    "id": "2",
    "tripUpdate": {
        "trip": {"tripId": "G10012026-01-05", "scheduleRelationship": "SCHEDULED"},
        "stopTimeUpdate": [
            {"stopId": "30200", "arrival": {"time": str(ZAMORA_EPOCH), "delay": 0}},
        ],
    },
}

# Trip que no corresponde a ningún tren monitorizado por este proyecto.
ENTITY_UNRELATED = {
    "id": "3",
    "tripUpdate": {
        "trip": {"tripId": "9999912026-01-05", "scheduleRelationship": "SCHEDULED"},
        "stopTimeUpdate": [
            {"stopId": "60000", "arrival": {"time": str(ZAMORA_EPOCH), "delay": 0}},
        ],
    },
}

# Dos entidades cuyo tripId empieza igual ("M100...") → colisión de prefijo,
# find_stop_time_update debe descartar por ambigüedad en vez de adivinar.
ENTITY_M100_COLLISION_A = {
    "id": "4a",
    "tripUpdate": {
        "trip": {"tripId": "M10012026-01-05", "scheduleRelationship": "SCHEDULED"},
        "stopTimeUpdate": [{"stopId": "17000", "arrival": {"time": str(CHAMARTIN_EPOCH), "delay": 60}}],
    },
}
ENTITY_M100_COLLISION_B = {
    "id": "4b",
    "tripUpdate": {
        "trip": {"tripId": "M10022026-01-05", "scheduleRelationship": "SCHEDULED"},
        "stopTimeUpdate": [{"stopId": "17000", "arrival": {"time": str(CHAMARTIN_EPOCH), "delay": 90}}],
    },
}

# Trip de M100 encontrado, pero sin ningún stopTimeUpdate para Zamora.
ENTITY_M100_NO_ZAMORA_STOP = {
    "id": "5",
    "tripUpdate": {
        "trip": {"tripId": "M10012026-01-05", "scheduleRelationship": "SCHEDULED"},
        "stopTimeUpdate": [{"stopId": "17000", "arrival": {"time": str(CHAMARTIN_EPOCH), "delay": 60}}],
    },
}

# Campos anidados ausentes/malformados a distintos niveles.
ENTITY_MISSING_TRIP_UPDATE = {"id": "6"}
ENTITY_MISSING_TRIP = {"id": "7", "tripUpdate": {}}
ENTITY_MISSING_TRIP_ID = {"id": "8", "tripUpdate": {"trip": {}}}
ENTITY_MISSING_STOP_TIME_UPDATE = {
    "id": "9",
    "tripUpdate": {"trip": {"tripId": "M10012026-01-05"}},
}
ENTITY_MISSING_ARRIVAL = {
    "id": "10",
    "tripUpdate": {
        "trip": {"tripId": "M10012026-01-05"},
        "stopTimeUpdate": [{"stopId": "30200"}],
    },
}
ENTITY_NON_NUMERIC_DELAY = {
    "id": "11",
    "tripUpdate": {
        "trip": {"tripId": "M10012026-01-05"},
        "stopTimeUpdate": [{"stopId": "30200", "arrival": {"time": str(ZAMORA_EPOCH), "delay": "not-a-number"}}],
    },
}
ENTITY_NON_NUMERIC_EPOCH = {
    "id": "12",
    "tripUpdate": {
        "trip": {"tripId": "M10012026-01-05"},
        "stopTimeUpdate": [{"stopId": "30200", "arrival": {"time": "not-an-epoch", "delay": 0}}],
    },
}

TRIP_UPDATES_RESPONSE_SAMPLE = {
    "header": {"gtfsRealtimeVersion": "2.0", "timestamp": "1767598000"},
    "entity": [ENTITY_M100, ENTITY_G100, ENTITY_UNRELATED],
}
