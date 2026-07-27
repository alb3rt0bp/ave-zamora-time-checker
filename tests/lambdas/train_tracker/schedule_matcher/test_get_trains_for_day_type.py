import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from schedule_matcher import ScheduleMatcher

CONFIG = {
    "trains": [
        {"cod_comercial": "M100", "tipo_dia": "laborable"},
        {"cod_comercial": "G100", "tipo_dia": "laborable"},
        {"cod_comercial": "M200", "tipo_dia": "domingo"},
    ]
}


class TestGetTrainsForDayType(unittest.TestCase):
    def setUp(self):
        self.matcher = ScheduleMatcher(CONFIG, SAMPLE_LOG_EXTRA)

    def test_filters_laborable(self):
        result = self.matcher.get_trains_for_day_type("laborable")
        self.assertEqual([t["cod_comercial"] for t in result], ["M100", "G100"])

    def test_filters_domingo(self):
        result = self.matcher.get_trains_for_day_type("domingo")
        self.assertEqual([t["cod_comercial"] for t in result], ["M200"])

    def test_no_match_returns_empty_list(self):
        result = self.matcher.get_trains_for_day_type("sabado")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
