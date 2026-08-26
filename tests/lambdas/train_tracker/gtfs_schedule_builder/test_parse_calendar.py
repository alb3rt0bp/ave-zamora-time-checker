import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.reference_dates import MONDAY
from tests.dummies.gtfs_samples import CALENDAR_CSV

from gtfs_schedule_builder import _parse_calendar


class TestParseCalendar(unittest.TestCase):
    def test_active_service_within_date_range_on_matching_weekday(self):
        result = _parse_calendar(CALENDAR_CSV, {"SVC_LABORABLE"}, MONDAY)

        self.assertTrue(result["SVC_LABORABLE"])

    def test_inactive_when_weekday_column_is_zero(self):
        # SVC_SUNDAY_ONLY tiene toda la semana a 0; su único día activo lo da
        # calendar_dates.txt, no este fichero.
        result = _parse_calendar(CALENDAR_CSV, {"SVC_SUNDAY_ONLY"}, MONDAY)

        self.assertFalse(result["SVC_SUNDAY_ONLY"])

    def test_inactive_when_target_date_outside_range(self):
        result = _parse_calendar(CALENDAR_CSV, {"SVC_OUTOFRANGE"}, MONDAY)

        self.assertFalse(result["SVC_OUTOFRANGE"])

    def test_ignores_service_ids_not_requested(self):
        result = _parse_calendar(CALENDAR_CSV, {"SVC_LABORABLE"}, MONDAY)

        self.assertNotIn("SVC_SUNDAY_ONLY", result)

    def test_service_id_absent_from_calendar_file_is_absent_from_result(self):
        result = _parse_calendar(CALENDAR_CSV, {"SVC_NEVER_DEFINED"}, MONDAY)

        self.assertEqual(result, {})

    def test_tolerates_padded_header_on_last_column(self):
        # Regresión: el feed real de Renfe rellena cada fila (cabecera
        # incluida) con espacios de cola hasta un ancho fijo. Si no se
        # recortan también las CLAVES del DictReader, la última columna
        # ("end_date") queda con una clave corrupta y row.get("end_date")
        # siempre cae al valor por defecto → in_range da False siempre,
        # aunque la fecha esté claramente dentro de rango.
        padded_csv = (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
            "start_date,end_date" + (" " * 40) + "\n"
            "SVC_PADDED,1,1,1,1,1,1,1,20260101,20260131" + (" " * 40) + "\n"
        )

        result = _parse_calendar(padded_csv, {"SVC_PADDED"}, MONDAY)

        self.assertTrue(result["SVC_PADDED"])


if __name__ == "__main__":
    unittest.main()
