import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.reference_dates import MONDAY, SUNDAY
from tests.dummies.gtfs_samples import CALENDAR_DATES_CSV

from gtfs_schedule_builder import _parse_calendar_dates


class TestParseCalendarDates(unittest.TestCase):
    def test_exception_type_1_is_added(self):
        result = _parse_calendar_dates(CALENDAR_DATES_CSV, {"SVC_SUNDAY_ONLY"}, SUNDAY)

        self.assertEqual(result, {"SVC_SUNDAY_ONLY": True})

    def test_exception_type_2_is_removed(self):
        result = _parse_calendar_dates(CALENDAR_DATES_CSV, {"SVC_REMOVED_TODAY"}, MONDAY)

        self.assertEqual(result, {"SVC_REMOVED_TODAY": False})

    def test_no_exception_for_target_date_is_absent_from_result(self):
        # SVC_SUNDAY_ONLY tiene excepción para SUNDAY, no para MONDAY.
        result = _parse_calendar_dates(CALENDAR_DATES_CSV, {"SVC_SUNDAY_ONLY"}, MONDAY)

        self.assertEqual(result, {})

    def test_ignores_service_ids_not_requested(self):
        result = _parse_calendar_dates(CALENDAR_DATES_CSV, {"SVC_REMOVED_TODAY"}, MONDAY)

        self.assertNotIn("SVC_SUNDAY_ONLY", result)

    def test_tolerates_padded_header_on_last_column(self):
        # Regresión: exception_type es la última columna de calendar_dates.txt,
        # justo la que este módulo necesita leer — ver el mismo caso en
        # test_parse_calendar.py para el porqué del padding en la cabecera.
        padded_csv = (
            "service_id,date,exception_type" + (" " * 40) + "\n"
            "SVC_PADDED,20260105,1" + (" " * 40) + "\n"
        )

        result = _parse_calendar_dates(padded_csv, {"SVC_PADDED"}, MONDAY)

        self.assertEqual(result, {"SVC_PADDED": True})


if __name__ == "__main__":
    unittest.main()
