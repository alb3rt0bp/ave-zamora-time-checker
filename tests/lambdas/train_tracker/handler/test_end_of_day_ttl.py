import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")


class TestEndOfDayTtl(HandlerTestCase):
    def test_matches_02_30_next_day_with_default_night_tail_window(self):
        # NIGHT_TAIL_WINDOW_HOURS por defecto = 2 → corte a las 2:30 del día
        # siguiente a `today` (30 min de margen tras el tramo de madrugada).
        next_day = MONDAY + timedelta(days=1)
        expected = datetime(next_day.year, next_day.month, next_day.day, 2, 30, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        self.assertEqual(ttl, int(expected.timestamp()))

    def test_is_always_in_the_future_relative_to_end_of_today(self):
        end_of_today = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 23, 58, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        self.assertGreater(ttl, int(end_of_today.timestamp()))

    @patch("handler.NIGHT_TAIL_WINDOW_HOURS", 4)
    def test_follows_a_wider_night_tail_window(self):
        # El corte de TTL debe seguir a NIGHT_TAIL_WINDOW_HOURS si se
        # amplía el tramo de polling de madrugada (p. ej. a 4h → corte 4:30).
        next_day = MONDAY + timedelta(days=1)
        expected = datetime(next_day.year, next_day.month, next_day.day, 4, 30, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        self.assertEqual(ttl, int(expected.timestamp()))


if __name__ == "__main__":
    unittest.main()
