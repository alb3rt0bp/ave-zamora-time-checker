import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")


class TestEndOfDayTtl(HandlerTestCase):
    def test_matches_23_59_59_same_day(self):
        now_local = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 15, tzinfo=TZ)
        expected = datetime(
            MONDAY.year, MONDAY.month, MONDAY.day, 23, 59, 59, tzinfo=TZ
        )

        ttl = self.handler._end_of_day_ttl(now_local)

        self.assertEqual(ttl, int(expected.timestamp()))

    def test_is_always_in_the_future_relative_to_now(self):
        now_local = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 23, 58, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(now_local)

        self.assertGreater(ttl, int(now_local.timestamp()))


if __name__ == "__main__":
    unittest.main()
