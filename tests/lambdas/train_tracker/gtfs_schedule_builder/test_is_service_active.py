import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup

from gtfs_schedule_builder import _is_service_active


class TestIsServiceActive(unittest.TestCase):
    def test_uses_calendar_default_when_no_exception(self):
        self.assertTrue(_is_service_active("S1", {"S1": True}, {}))
        self.assertFalse(_is_service_active("S1", {"S1": False}, {}))

    def test_exception_overrides_calendar_default_to_active(self):
        self.assertTrue(_is_service_active("S1", {"S1": False}, {"S1": True}))

    def test_exception_overrides_calendar_default_to_inactive(self):
        self.assertFalse(_is_service_active("S1", {"S1": True}, {"S1": False}))

    def test_service_absent_from_calendar_defaults_to_inactive(self):
        # Un service_id definido solo por calendar_dates.txt (sin fila en
        # calendar.txt) es válido en GTFS; sin excepción para hoy, inactivo.
        self.assertFalse(_is_service_active("S1", {}, {}))

    def test_service_absent_from_calendar_but_added_by_exception(self):
        self.assertTrue(_is_service_active("S1", {}, {"S1": True}))


if __name__ == "__main__":
    unittest.main()
