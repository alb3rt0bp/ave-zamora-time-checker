import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from datalake_writer import DatalakeWriter


class TestBuildKey(unittest.TestCase):
    def setUp(self):
        self.writer = DatalakeWriter(object(), "my-bucket", SAMPLE_LOG_EXTRA)

    def test_builds_hive_partitioned_key(self):
        ts = datetime(2026, 1, 5, 7, 41, 23, tzinfo=ZoneInfo("Europe/Madrid"))

        key = self.writer._build_key("M100", "Madrid", ts)

        self.assertEqual(
            key, "zamora-trains/year=2026/month=01/day=05/M100_Madrid_20260105T074123.json"
        )

    def test_pads_single_digit_month_and_day(self):
        ts = datetime(2026, 3, 2, 9, 0, 0, tzinfo=ZoneInfo("Europe/Madrid"))

        key = self.writer._build_key("G100", "Galicia", ts)

        self.assertIn("year=2026/month=03/day=02/", key)


if __name__ == "__main__":
    unittest.main()
