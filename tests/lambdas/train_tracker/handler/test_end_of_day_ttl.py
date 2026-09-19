import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")


class TestEndOfDayTtl(HandlerTestCase):
    def test_matches_02_30_two_days_later_with_the_default_margin(self):
        # NIGHT_TAIL_WINDOW_HOURS = 2 y STATE_TTL_MARGIN_DAYS = 1 (valores por
        # defecto) → corte a las 2:30 de today+2.
        cutoff_day = MONDAY + timedelta(days=2)
        expected = datetime(cutoff_day.year, cutoff_day.month, cutoff_day.day, 2, 30, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        self.assertEqual(ttl, int(expected.timestamp()))

    def test_survives_the_daily_dump_of_the_next_day_with_a_wide_margin(self):
        # Regresión del 2026-09-18: el TTL expiraba 15 min después del
        # volcado (02:30 vs 02:15), así que un cambio de la propia fórmula
        # desplegado a media tarde dejó los items del día expirando ANTES de
        # volcarlos. El estado debe sobrevivir holgadamente al volcado.
        dump_day = MONDAY + timedelta(days=1)
        dump_run = datetime(dump_day.year, dump_day.month, dump_day.day, 2, 15, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        margin_hours = (ttl - int(dump_run.timestamp())) / 3600
        self.assertGreaterEqual(margin_hours, 24)

    def test_is_always_in_the_future_relative_to_end_of_today(self):
        end_of_today = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 23, 58, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        self.assertGreater(ttl, int(end_of_today.timestamp()))

    @patch("handler.NIGHT_TAIL_WINDOW_HOURS", 4)
    def test_follows_a_wider_night_tail_window(self):
        # La hora del corte sigue a NIGHT_TAIL_WINDOW_HOURS si se amplía el
        # tramo de polling de madrugada (p. ej. a 4h → corte 4:30).
        cutoff_day = MONDAY + timedelta(days=2)
        expected = datetime(cutoff_day.year, cutoff_day.month, cutoff_day.day, 4, 30, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        self.assertEqual(ttl, int(expected.timestamp()))

    @patch("handler.STATE_TTL_MARGIN_DAYS", 3)
    def test_follows_a_wider_ttl_margin(self):
        cutoff_day = MONDAY + timedelta(days=4)
        expected = datetime(cutoff_day.year, cutoff_day.month, cutoff_day.day, 2, 30, tzinfo=TZ)

        ttl = self.handler._end_of_day_ttl(MONDAY)

        self.assertEqual(ttl, int(expected.timestamp()))


if __name__ == "__main__":
    unittest.main()
