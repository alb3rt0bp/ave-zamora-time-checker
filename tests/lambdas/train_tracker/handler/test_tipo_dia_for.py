import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY, SATURDAY, SUNDAY

TZ = ZoneInfo("Europe/Madrid")


class TestTipoDiaFor(HandlerTestCase):
    def test_monday_is_laborable(self):
        now = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 12, 0, tzinfo=TZ)
        self.assertEqual(self.handler._tipo_dia_for(now), "laborable")

    def test_saturday_is_sabado(self):
        now = datetime(SATURDAY.year, SATURDAY.month, SATURDAY.day, 12, 0, tzinfo=TZ)
        self.assertEqual(self.handler._tipo_dia_for(now), "sabado")

    def test_sunday_is_domingo(self):
        now = datetime(SUNDAY.year, SUNDAY.month, SUNDAY.day, 12, 0, tzinfo=TZ)
        self.assertEqual(self.handler._tipo_dia_for(now), "domingo")


if __name__ == "__main__":
    unittest.main()
