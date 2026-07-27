import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 0, tzinfo=TZ)


class TestGetState(HandlerTestCase):
    def test_returns_none_when_no_item_exists(self):
        result = self.handler._get_state("M100", NOW)
        self.assertIsNone(result)

    def test_returns_item_when_it_exists(self):
        self.table.put_item(
            Item={"pk": f"M100#{NOW.date().isoformat()}", "sk": "TRACKING", "done": False}
        )

        result = self.handler._get_state("M100", NOW)

        self.assertEqual(result["done"], False)

    def test_keyed_by_cod_and_date(self):
        self.table.put_item(
            Item={"pk": "M100#2026-01-04", "sk": "TRACKING", "done": True}
        )

        result = self.handler._get_state("M100", NOW)  # NOW es 2026-01-05

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
