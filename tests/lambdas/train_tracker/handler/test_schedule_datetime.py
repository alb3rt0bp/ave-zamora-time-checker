import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")


class TestScheduleDatetime(HandlerTestCase):
    def test_anchors_hhmm_on_the_given_date(self):
        result = self.handler._schedule_datetime(MONDAY, "08:30", TZ)

        self.assertEqual(result, datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 30, tzinfo=TZ))

    def test_anchors_on_today_even_when_now_is_already_the_next_calendar_day(self):
        # El caso que motiva esta función: durante el tramo de madrugada,
        # now_local ya está en el día calendario siguiente, pero la hora
        # programada de un tren de "hoy" (día operativo) debe seguir
        # anclada en ese día operativo, no en el de "ahora".
        result = self.handler._schedule_datetime(MONDAY, "23:07", TZ)

        self.assertEqual(result.date(), MONDAY)
        self.assertEqual(result.strftime("%H:%M"), "23:07")

    def test_arithmetic_on_the_result_rolls_over_to_the_next_day_correctly(self):
        from datetime import timedelta
        result = self.handler._schedule_datetime(MONDAY, "23:07", TZ) + timedelta(minutes=80)

        expected_day = MONDAY + timedelta(days=1)
        self.assertEqual(result.date(), expected_day)
        self.assertEqual(result.strftime("%H:%M"), "00:27")


if __name__ == "__main__":
    unittest.main()
