import unittest
from datetime import date

from tests.dummies import api_env  # noqa: F401 - sys.path/env setup

from gtfs_schedule_reference import build_schedule_reference

ZAMORA_CODE = "30200"
CHAMARTIN_CODE = "17000"

# 2026-06-15: cualquier fecha dentro del rango vigente de SVC_WEEKDAY/
# SVC_WEEKEND y fuera del de SVC_EXPIRED/SVC_FUTURE — build_schedule_reference
# no mira el día de la semana de reference_date, solo si cae dentro del
# start_date/end_date de cada servicio, así que el día concreto es arbitrario.
REFERENCE_DATE = date(2026, 6, 15)

STOP_TIMES_CSV = """trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled
TRIP_M1,7:39:00,7:41:00,30200,04,,0,0,
TRIP_M1,8:49:00,8:49:00,17000,05,,1,0,
TRIP_G1,10:04:00,10:04:00,17000,01,,0,1,
TRIP_G1,11:08:00,11:10:00,30200,02,,0,0,
TRIP_D1,7:39:00,7:41:00,30200,04,,0,0,
TRIP_D1,8:49:00,8:49:00,17000,05,,1,0,
TRIP_D2,7:39:00,7:41:00,30200,02,,0,0,
TRIP_D2,8:49:00,8:49:00,17000,03,,1,0,
TRIP_EXPIRED,7:00:00,7:02:00,30200,01,,0,0,
TRIP_EXPIRED,8:00:00,8:00:00,17000,02,,1,0,
TRIP_FUTURE,7:00:00,7:02:00,30200,01,,0,0,
TRIP_FUTURE,8:00:00,8:00:00,17000,02,,1,0,
TRIP_NOSHORTNAME,7:00:00,7:02:00,30200,01,,0,0,
TRIP_NOSHORTNAME,8:00:00,8:00:00,17000,02,,1,0,
TRIP_NOCHAM,9:00:00,9:00:00,30200,01,,0,1,
"""

TRIPS_CSV = """route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id,wheelchair_accessible
R1,SVC_WEEKDAY,TRIP_M1,,04154,,,,1
R2,SVC_WEEKEND,TRIP_G1,,04505,,,,1
R3,SVC_WEEKDAY,TRIP_D1,,04999,,,,1
R3,SVC_WEEKDAY,TRIP_D2,,04999,,,,1
R4,SVC_EXPIRED,TRIP_EXPIRED,,04222,,,,1
R5,SVC_FUTURE,TRIP_FUTURE,,04333,,,,1
R6,SVC_WEEKDAY,TRIP_NOSHORTNAME,,,,,,1
R7,SVC_WEEKDAY,TRIP_NOCHAM,,04001,,,,1
"""

# start_date/end_date deliberadamente distintos de calendar_dates.txt: esta
# función ignora calendar_dates.txt por completo (ver docstring del módulo),
# así que ni siquiera hace falta incluirlo en gtfs_files para estos tests.
CALENDAR_CSV = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
SVC_WEEKDAY,1,1,1,1,1,0,0,20260101,20261231
SVC_WEEKEND,0,0,0,0,0,1,1,20260101,20261231
SVC_EXPIRED,1,1,1,1,1,0,0,20250101,20251231
SVC_FUTURE,1,1,1,1,1,0,0,20270101,20271231
"""

GTFS_FILES = {
    "stop_times.txt": STOP_TIMES_CSV,
    "trips.txt": TRIPS_CSV,
    "calendar.txt": CALENDAR_CSV,
}


class TestBuildScheduleReference(unittest.TestCase):
    def _build(self):
        return build_schedule_reference(GTFS_FILES, REFERENCE_DATE, ZAMORA_CODE, CHAMARTIN_CODE, {})

    def test_resolves_madrid_and_galicia_trains_with_their_weekly_pattern(self):
        result = self._build()
        by_cod = {t["cod_comercial"]: t for t in result}

        self.assertEqual(by_cod["04154"], {
            "cod_comercial": "04154", "sentido": "Madrid",
            "hora_salida": "07:41", "hora_llegada_destino": "08:49",
            "weekdays": [0, 1, 2, 3, 4],
        })
        self.assertEqual(by_cod["04505"], {
            "cod_comercial": "04505", "sentido": "Galicia",
            "hora_salida": "10:04", "hora_llegada_destino": "11:08",
            "weekdays": [5, 6],
        })

    def test_dedups_double_composition_trips_into_one_entry(self):
        result = self._build()
        matching = [t for t in result if t["cod_comercial"] == "04999"]

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["weekdays"], [0, 1, 2, 3, 4])

    def test_excludes_service_whose_date_range_does_not_cover_reference_date(self):
        result = self._build()
        codes = {t["cod_comercial"] for t in result}

        self.assertNotIn("04222", codes)  # SVC_EXPIRED: end_date en el pasado
        self.assertNotIn("04333", codes)  # SVC_FUTURE: start_date en el futuro

    def test_excludes_trip_without_trip_short_name(self):
        result = self._build()
        # TRIP_NOSHORTNAME no tiene cod_comercial que asignar, así que ni
        # siquiera puede aparecer con un código vacío.
        self.assertTrue(all(t["cod_comercial"] for t in result))

    def test_excludes_trip_that_never_stops_at_chamartin(self):
        result = self._build()
        codes = {t["cod_comercial"] for t in result}

        self.assertNotIn("04001", codes)

    def test_sorted_by_cod_comercial(self):
        result = self._build()
        self.assertEqual([t["cod_comercial"] for t in result], sorted(t["cod_comercial"] for t in result))

    def test_does_not_require_calendar_dates_txt(self):
        # A diferencia de build_todays_trains, esta función deriva el patrón
        # semanal solo de calendar.txt — calendar_dates.txt ni siquiera se
        # lee, así que gtfs_files puede omitirlo sin error.
        self.assertNotIn("calendar_dates.txt", GTFS_FILES)
        result = self._build()
        self.assertTrue(len(result) > 0)


if __name__ == "__main__":
    unittest.main()
