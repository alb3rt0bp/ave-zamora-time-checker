import unittest
from datetime import date

from tests.dummies import api_env  # noqa: F401 - sys.path/env setup

from gtfs_schedule_reference import _parse_calendar_weekdays

CALENDAR_CSV = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
SVC_WEEKDAY,1,1,1,1,1,0,0,20260101,20261231
SVC_WEEKEND,0,0,0,0,0,1,1,20260101,20261231
SVC_EXPIRED,1,1,1,1,1,0,0,20250101,20251231
SVC_NO_DAYS,0,0,0,0,0,0,0,20260101,20261231
SVC_NOT_OF_INTEREST,1,1,1,1,1,1,1,20260101,20261231
SVC_DECOY_VIA_EXCEPTIONS,1,1,1,1,1,1,1,20260610,20260621
"""

# calendar.txt marca SVC_DECOY_VIA_EXCEPTIONS activo los 7 días de la semana
# (como casi todos los servicios en el feed real de Renfe — ver docstring de
# gtfs_schedule_reference.py) — se retiran aquí los 8 días laborables del
# intervalo 10-21 junio 2026, dejando activos solo sábado (13,20) y domingo
# (14,21).
CALENDAR_DATES_CSV = """service_id,date,exception_type
SVC_DECOY_VIA_EXCEPTIONS,20260610,2
SVC_DECOY_VIA_EXCEPTIONS,20260611,2
SVC_DECOY_VIA_EXCEPTIONS,20260612,2
SVC_DECOY_VIA_EXCEPTIONS,20260615,2
SVC_DECOY_VIA_EXCEPTIONS,20260616,2
SVC_DECOY_VIA_EXCEPTIONS,20260617,2
SVC_DECOY_VIA_EXCEPTIONS,20260618,2
SVC_DECOY_VIA_EXCEPTIONS,20260619,2
"""

REFERENCE_DATE = date(2026, 6, 15)
SERVICE_IDS = {"SVC_WEEKDAY", "SVC_WEEKEND", "SVC_EXPIRED", "SVC_NO_DAYS", "SVC_DECOY_VIA_EXCEPTIONS"}


class TestParseCalendarWeekdays(unittest.TestCase):
    def _parse(self):
        return _parse_calendar_weekdays(CALENDAR_CSV, CALENDAR_DATES_CSV, SERVICE_IDS, REFERENCE_DATE)

    def test_returns_active_weekdays_for_services_within_range(self):
        result = self._parse()

        self.assertEqual(result["SVC_WEEKDAY"], [0, 1, 2, 3, 4])
        self.assertEqual(result["SVC_WEEKEND"], [5, 6])

    def test_excludes_service_out_of_date_range(self):
        result = self._parse()

        self.assertNotIn("SVC_EXPIRED", result)

    def test_excludes_service_with_no_active_weekday(self):
        result = self._parse()

        self.assertNotIn("SVC_NO_DAYS", result)

    def test_ignores_service_ids_not_of_interest(self):
        result = self._parse()

        self.assertNotIn("SVC_NOT_OF_INTEREST", result)

    def test_derives_pattern_from_calendar_dates_when_calendar_txt_is_a_decoy(self):
        """
        calendar.txt marca SVC_DECOY_VIA_EXCEPTIONS activo los 7 días de la
        semana; sin aplicar calendar_dates.txt el resultado sería
        [0,1,2,3,4,5,6] en vez del patrón real (solo sábado/domingo).
        """
        result = self._parse()

        self.assertEqual(result["SVC_DECOY_VIA_EXCEPTIONS"], [5, 6])


if __name__ == "__main__":
    unittest.main()
