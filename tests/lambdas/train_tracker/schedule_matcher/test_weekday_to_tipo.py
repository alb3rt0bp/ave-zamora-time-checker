import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from schedule_matcher import ScheduleMatcher


class TestWeekdayToTipo(unittest.TestCase):
    def setUp(self):
        self.matcher = ScheduleMatcher({"trains": []}, SAMPLE_LOG_EXTRA)

    def test_monday_to_friday_is_laborable(self):
        for weekday in range(0, 5):
            self.assertEqual(self.matcher._weekday_to_tipo(weekday), "laborable")

    def test_saturday_is_sabado(self):
        self.assertEqual(self.matcher._weekday_to_tipo(5), "sabado")

    def test_sunday_is_domingo(self):
        self.assertEqual(self.matcher._weekday_to_tipo(6), "domingo")


if __name__ == "__main__":
    unittest.main()
