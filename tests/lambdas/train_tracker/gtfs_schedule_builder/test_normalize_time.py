import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup

from gtfs_schedule_builder import _normalize_time


class TestNormalizeTime(unittest.TestCase):
    def test_pads_single_digit_hour(self):
        self.assertEqual(_normalize_time("7:41:00"), "07:41")

    def test_keeps_two_digit_hour(self):
        self.assertEqual(_normalize_time("14:05:00"), "14:05")

    def test_drops_seconds(self):
        self.assertEqual(_normalize_time("08:49:30"), "08:49")

    def test_wraps_past_midnight_hours(self):
        # GTFS permite horas >=24 para servicios que cruzan la medianoche;
        # este sistema no modela ese cruce, solo envuelve al día siguiente.
        self.assertEqual(_normalize_time("25:10:00"), "01:10")

    def test_strips_surrounding_whitespace(self):
        # El feed real de Renfe rellena las filas con espacios de cola.
        self.assertEqual(_normalize_time("  7:41:00   "), "07:41")


if __name__ == "__main__":
    unittest.main()
