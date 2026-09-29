import unittest
from datetime import date

from tests.dummies import api_env  # noqa: F401 - sys.path/env setup

from gtfs_schedule_reference import build_schedule_reference

ZAMORA_CODE = "30200"
CHAMARTIN_CODE = "17000"

# 2026-06-15 (lunes): dentro del rango vigente de SVC_WEEKDAY_VIA_EXCEPTIONS/
# SVC_SATSUN_VIA_EXCEPTIONS y fuera del de SVC_EXPIRED/SVC_FUTURE.
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
R1,SVC_WEEKDAY_VIA_EXCEPTIONS,TRIP_M1,,04154,,,,1
R2,SVC_SATSUN_VIA_EXCEPTIONS,TRIP_G1,,04505,,,,1
R3,SVC_WEEKDAY_VIA_EXCEPTIONS,TRIP_D1,,04999,,,,1
R3,SVC_WEEKDAY_VIA_EXCEPTIONS,TRIP_D2,,04999,,,,1
R4,SVC_EXPIRED,TRIP_EXPIRED,,04222,,,,1
R5,SVC_FUTURE,TRIP_FUTURE,,04333,,,,1
R6,SVC_WEEKDAY_VIA_EXCEPTIONS,TRIP_NOSHORTNAME,,,,,,1
R7,SVC_WEEKDAY_VIA_EXCEPTIONS,TRIP_NOCHAM,,04001,,,,1
"""

# Igual que en el feed real de Renfe (ver docstring de gtfs_schedule_reference.py):
# calendar.txt marca estos dos servicios activos TODOS los días de la semana
# (un valor señuelo) — el patrón real de cada uno vive en calendar_dates.txt.
CALENDAR_CSV = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
SVC_WEEKDAY_VIA_EXCEPTIONS,1,1,1,1,1,1,1,20260601,20260630
SVC_SATSUN_VIA_EXCEPTIONS,1,1,1,1,1,1,1,20260610,20260621
SVC_EXPIRED,1,1,1,1,1,0,0,20250101,20251231
SVC_FUTURE,1,1,1,1,1,0,0,20270101,20271231
"""

# SVC_WEEKDAY_VIA_EXCEPTIONS (junio 2026): se retiran los 8 fines de semana
# del mes (6,7,13,14,20,21,27,28), dejando activo solo lunes-viernes.
# SVC_SATSUN_VIA_EXCEPTIONS (10-21 junio 2026): se retiran los 8 días
# laborables del intervalo, dejando activos solo los sábados/domingos
# (13,14,20,21).
CALENDAR_DATES_CSV = """service_id,date,exception_type
SVC_WEEKDAY_VIA_EXCEPTIONS,20260606,2
SVC_WEEKDAY_VIA_EXCEPTIONS,20260607,2
SVC_WEEKDAY_VIA_EXCEPTIONS,20260613,2
SVC_WEEKDAY_VIA_EXCEPTIONS,20260614,2
SVC_WEEKDAY_VIA_EXCEPTIONS,20260620,2
SVC_WEEKDAY_VIA_EXCEPTIONS,20260621,2
SVC_WEEKDAY_VIA_EXCEPTIONS,20260627,2
SVC_WEEKDAY_VIA_EXCEPTIONS,20260628,2
SVC_SATSUN_VIA_EXCEPTIONS,20260610,2
SVC_SATSUN_VIA_EXCEPTIONS,20260611,2
SVC_SATSUN_VIA_EXCEPTIONS,20260612,2
SVC_SATSUN_VIA_EXCEPTIONS,20260615,2
SVC_SATSUN_VIA_EXCEPTIONS,20260616,2
SVC_SATSUN_VIA_EXCEPTIONS,20260617,2
SVC_SATSUN_VIA_EXCEPTIONS,20260618,2
SVC_SATSUN_VIA_EXCEPTIONS,20260619,2
"""

GTFS_FILES = {
    "stop_times.txt": STOP_TIMES_CSV,
    "trips.txt": TRIPS_CSV,
    "calendar.txt": CALENDAR_CSV,
    "calendar_dates.txt": CALENDAR_DATES_CSV,
}


class TestBuildScheduleReference(unittest.TestCase):
    def _build(self, gtfs_files: dict = GTFS_FILES):
        return build_schedule_reference(gtfs_files, REFERENCE_DATE, ZAMORA_CODE, CHAMARTIN_CODE, {})

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

    def test_resolves_real_pattern_when_calendar_txt_is_a_decoy(self):
        """
        calendar.txt marca SVC_SATSUN_VIA_EXCEPTIONS activo los 7 días de la
        semana — como ocurre casi siempre en el feed real de Renfe. Sin
        aplicar calendar_dates.txt, 04505 se resolvería (incorrectamente)
        como "circula todos los días" en vez de solo sábado/domingo. Esta es
        la regresión que motivó el fix: antes de él, esta función ignoraba
        calendar_dates.txt por completo.
        """
        result = self._build()
        by_cod = {t["cod_comercial"]: t for t in result}

        self.assertEqual(by_cod["04505"]["weekdays"], [5, 6])
        self.assertNotEqual(by_cod["04505"]["weekdays"], [0, 1, 2, 3, 4, 5, 6])

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


if __name__ == "__main__":
    unittest.main()
