import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")


def _at(day, hh, mm):
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ)


class TestOperationalDate(HandlerTestCase):
    """
    NIGHT_TAIL_WINDOW_MINUTES por defecto = 30 (ver handler.py):
    [00:00, 00:30) sigue perteneciendo operativamente al día calendario
    anterior.
    """

    def test_daytime_matches_calendar_date(self):
        self.assertEqual(self.handler._operational_date(_at(MONDAY, 8, 0)), MONDAY)

    def test_just_before_midnight_matches_calendar_date(self):
        self.assertEqual(self.handler._operational_date(_at(MONDAY, 23, 59)), MONDAY)

    def test_just_after_midnight_belongs_to_previous_day(self):
        next_day = MONDAY + timedelta(days=1)
        self.assertEqual(self.handler._operational_date(_at(next_day, 0, 0)), MONDAY)

    def test_end_of_tail_window_still_belongs_to_previous_day(self):
        # Último ciclo del tramo (00:25) y el minuto anterior al corte.
        next_day = MONDAY + timedelta(days=1)
        self.assertEqual(self.handler._operational_date(_at(next_day, 0, 25)), MONDAY)
        self.assertEqual(self.handler._operational_date(_at(next_day, 0, 29)), MONDAY)

    def test_at_tail_window_boundary_matches_calendar_date_again(self):
        next_day = MONDAY + timedelta(days=1)
        self.assertEqual(self.handler._operational_date(_at(next_day, 0, 30)), next_day)

    def test_after_the_tail_window_matches_calendar_date(self):
        # El volcado diario corre a la 01:00, ya fuera del tramo.
        next_day = MONDAY + timedelta(days=1)
        self.assertEqual(self.handler._operational_date(_at(next_day, 1, 0)), next_day)


if __name__ == "__main__":
    unittest.main()
