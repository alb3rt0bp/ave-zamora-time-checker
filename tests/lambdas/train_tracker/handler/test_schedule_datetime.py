import unittest
from datetime import datetime, timedelta
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

    def test_offset_dias_moves_the_hour_to_the_following_day(self):
        # La llegada de un tren que sale a las 23:05 y llega a las 00:10
        # pertenece al día SIGUIENTE al día operativo (offset_dias=1). Sin
        # esto, su ventana se compararía contra las 00:10 del propio día
        # operativo, ~24 h antes de tiempo.
        result = self.handler._schedule_datetime(MONDAY, "00:10", TZ, 1)

        self.assertEqual(result, datetime(MONDAY.year, MONDAY.month, MONDAY.day, 0, 10, tzinfo=TZ)
                         + timedelta(days=1))
        self.assertEqual(result.strftime("%H:%M"), "00:10")

    def test_offset_dias_defaults_to_the_operational_day(self):
        self.assertEqual(
            self.handler._schedule_datetime(MONDAY, "08:30", TZ),
            self.handler._schedule_datetime(MONDAY, "08:30", TZ, 0),
        )

    def test_arithmetic_on_the_result_rolls_over_to_the_next_day_correctly(self):
        from datetime import timedelta
        result = self.handler._schedule_datetime(MONDAY, "23:07", TZ) + timedelta(minutes=80)

        expected_day = MONDAY + timedelta(days=1)
        self.assertEqual(result.date(), expected_day)
        self.assertEqual(result.strftime("%H:%M"), "00:27")


if __name__ == "__main__":
    unittest.main()
