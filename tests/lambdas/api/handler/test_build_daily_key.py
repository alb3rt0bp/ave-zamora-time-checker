import unittest
from datetime import date

from tests.dummies import api_env


class TestBuildDailyKey(unittest.TestCase):
    def setUp(self):
        self.handler = api_env.import_api_handler()

    def test_builds_hive_partitioned_key(self):
        key = self.handler._build_daily_key(date(2026, 1, 5))

        self.assertEqual(key, "zamora-trains/year=2026/month=01/day=05/2026-01-05.jsonl")

    def test_pads_single_digit_month_and_day(self):
        key = self.handler._build_daily_key(date(2026, 3, 2))

        self.assertIn("year=2026/month=03/day=02/", key)


if __name__ == "__main__":
    unittest.main()
