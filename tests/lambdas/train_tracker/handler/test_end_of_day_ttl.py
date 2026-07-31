import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")


class TestEndOfDayTtl(HandlerTestCase):
    def test_matches_00_30_next_day(self):
        now_local = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 15, tzinfo=TZ)
        next_day = MONDAY + timedelta(days=1)
        expected = datetime(next_day.year, next_day.month, next_day.day, 0, 30, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(now_local)

        self.assertEqual(ttl, int(expected.timestamp()))

    def test_is_always_in_the_future_relative_to_now(self):
        now_local = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 23, 58, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(now_local)

        self.assertGreater(ttl, int(now_local.timestamp()))

    def test_still_in_the_future_just_after_midnight(self):
        # 00:10 del día siguiente sigue estando antes del corte (00:30).
        next_day = MONDAY + timedelta(days=1)
        now_local = datetime(next_day.year, next_day.month, next_day.day, 0, 10, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(now_local)

        self.assertGreater(ttl, int(now_local.timestamp()))


if __name__ == "__main__":
    unittest.main()
