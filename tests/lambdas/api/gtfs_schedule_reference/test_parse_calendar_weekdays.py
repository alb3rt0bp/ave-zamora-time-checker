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
"""

REFERENCE_DATE = date(2026, 6, 15)
SERVICE_IDS = {"SVC_WEEKDAY", "SVC_WEEKEND", "SVC_EXPIRED", "SVC_NO_DAYS"}


class TestParseCalendarWeekdays(unittest.TestCase):
    def test_returns_active_weekdays_for_services_within_range(self):
        result = _parse_calendar_weekdays(CALENDAR_CSV, SERVICE_IDS, REFERENCE_DATE)

        self.assertEqual(result["SVC_WEEKDAY"], [0, 1, 2, 3, 4])
        self.assertEqual(result["SVC_WEEKEND"], [5, 6])

    def test_excludes_service_out_of_date_range(self):
        result = _parse_calendar_weekdays(CALENDAR_CSV, SERVICE_IDS, REFERENCE_DATE)

        self.assertNotIn("SVC_EXPIRED", result)

    def test_excludes_service_with_no_active_weekday(self):
        result = _parse_calendar_weekdays(CALENDAR_CSV, SERVICE_IDS, REFERENCE_DATE)

        self.assertNotIn("SVC_NO_DAYS", result)

    def test_ignores_service_ids_not_of_interest(self):
        result = _parse_calendar_weekdays(CALENDAR_CSV, SERVICE_IDS, REFERENCE_DATE)

        self.assertNotIn("SVC_NOT_OF_INTEREST", result)


if __name__ == "__main__":
    unittest.main()
