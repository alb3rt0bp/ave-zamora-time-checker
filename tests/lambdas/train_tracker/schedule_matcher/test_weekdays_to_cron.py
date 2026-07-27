import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup

from schedule_matcher import ScheduleMatcher


class TestWeekdaysToCron(unittest.TestCase):
    def test_monday_only(self):
        # Python 0=lunes → EventBridge dow 2
        result = ScheduleMatcher._weekdays_to_cron([0], 7, 11)
        self.assertEqual(result, "cron(11 7 ? * 2 *)")

    def test_sorts_and_maps_multiple_days(self):
        # lunes(0)->2, miércoles(2)->4, domingo(6)->1
        result = ScheduleMatcher._weekdays_to_cron([6, 0, 2], 8, 0)
        self.assertEqual(result, "cron(0 8 ? * 1,2,4 *)")


if __name__ == "__main__":
    unittest.main()
