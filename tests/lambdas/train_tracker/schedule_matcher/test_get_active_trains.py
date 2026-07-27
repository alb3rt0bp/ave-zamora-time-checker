import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY, SUNDAY

from schedule_matcher import ScheduleMatcher

TZ = ZoneInfo("Europe/Madrid")

CONFIG = {
    "trains": [
        {
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_salida": "07:00",
            "hora_llegada_destino": "08:30",
        },
        {
            "cod_comercial": "G200",
            "sentido": "Galicia",
            "tipo_dia": "domingo",
            "hora_salida": "10:00",
            "hora_llegada_destino": "11:20",
        },
    ]
}


class TestGetActiveTrains(unittest.TestCase):
    def setUp(self):
        self.matcher = ScheduleMatcher(CONFIG, SAMPLE_LOG_EXTRA)

    def test_filters_by_day_type(self):
        now = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 7, 30, tzinfo=TZ)

        active = self.matcher.get_active_trains(now)

        self.assertEqual([t["cod_comercial"] for t in active], ["M100"])

    def test_sunday_only_returns_sunday_train(self):
        now = datetime(SUNDAY.year, SUNDAY.month, SUNDAY.day, 10, 30, tzinfo=TZ)

        active = self.matcher.get_active_trains(now)

        self.assertEqual([t["cod_comercial"] for t in active], ["G200"])

    def test_returns_empty_list_when_nothing_matches(self):
        now = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 23, 0, tzinfo=TZ)

        active = self.matcher.get_active_trains(now)

        self.assertEqual(active, [])

    def test_passes_state_lookup_through_to_window_calc(self):
        now = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 9, 0, tzinfo=TZ)
        lookup = lambda cod: {"ult_retraso": 20}

        active = self.matcher.get_active_trains(now, state_lookup=lookup)

        self.assertEqual([t["cod_comercial"] for t in active], ["M100"])


if __name__ == "__main__":
    unittest.main()
