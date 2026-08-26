import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.reference_dates import MONDAY, SATURDAY, SUNDAY

from gtfs_schedule_builder import _tipo_dia_for


class TestTipoDiaFor(unittest.TestCase):
    def test_monday_is_laborable(self):
        self.assertEqual(_tipo_dia_for(MONDAY), "laborable")

    def test_saturday_is_sabado(self):
        self.assertEqual(_tipo_dia_for(SATURDAY), "sabado")

    def test_sunday_is_domingo(self):
        self.assertEqual(_tipo_dia_for(SUNDAY), "domingo")


if __name__ == "__main__":
    unittest.main()
