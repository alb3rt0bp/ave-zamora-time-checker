import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup

from schedule_matcher import ScheduleMatcher


class TestSubtractMinutes(unittest.TestCase):
    def test_simple_subtraction(self):
        self.assertEqual(ScheduleMatcher._subtract_minutes(7, 41, 30), (7, 11))

    def test_wraps_around_midnight(self):
        self.assertEqual(ScheduleMatcher._subtract_minutes(0, 10, 30), (23, 40))

    def test_zero_delta_is_noop(self):
        self.assertEqual(ScheduleMatcher._subtract_minutes(10, 15, 0), (10, 15))


if __name__ == "__main__":
    unittest.main()
