import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from schedule_matcher import ScheduleMatcher

CONFIG = {
    "polling_window_minutes": 45,
    "trains": [{"cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable"}],
}


class TestScheduleMatcherInit(unittest.TestCase):
    def test_stores_trains(self):
        matcher = ScheduleMatcher(CONFIG, SAMPLE_LOG_EXTRA)
        self.assertEqual(matcher.trains, CONFIG["trains"])

    def test_stores_window_minutes(self):
        matcher = ScheduleMatcher(CONFIG, SAMPLE_LOG_EXTRA)
        self.assertEqual(matcher.window_minutes, 45)

    def test_window_minutes_defaults_to_30(self):
        matcher = ScheduleMatcher({"trains": []}, SAMPLE_LOG_EXTRA)
        self.assertEqual(matcher.window_minutes, 30)

    def test_stores_log_extra(self):
        matcher = ScheduleMatcher(CONFIG, SAMPLE_LOG_EXTRA)
        self.assertEqual(matcher.log_extra, SAMPLE_LOG_EXTRA)


if __name__ == "__main__":
    unittest.main()
