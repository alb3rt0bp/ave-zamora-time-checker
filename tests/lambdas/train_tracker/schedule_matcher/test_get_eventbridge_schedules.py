import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from schedule_matcher import ScheduleMatcher

CONFIG = {
    "polling_window_minutes": 30,
    "trains": [
        {
            "cod_comercial": "M100",
            "tipo_dia": "laborable",
            "weekdays": [0, 1, 2, 3, 4],
            "hora_salida": "07:41",
        },
        {
            # Mismo cod_comercial + tipo_dia → debe deduplicarse.
            "cod_comercial": "M100",
            "tipo_dia": "laborable",
            "weekdays": [0, 1, 2, 3, 4],
            "hora_salida": "07:41",
        },
    ],
}


class TestGetEventbridgeSchedules(unittest.TestCase):
    def setUp(self):
        self.matcher = ScheduleMatcher(CONFIG, SAMPLE_LOG_EXTRA)

    def test_deduplicates_by_train_and_tipo_dia(self):
        rules = self.matcher.get_eventbridge_schedules()
        self.assertEqual(len(rules), 1)

    def test_rule_shape(self):
        rules = self.matcher.get_eventbridge_schedules()
        rule = rules[0]
        self.assertEqual(rule["name"], "zamora-train-M100-laborable")
        self.assertEqual(rule["timezone"], "Europe/Madrid")
        # hora_salida 07:41 - 30 min = 07:11
        self.assertEqual(rule["schedule_expression"], "cron(11 7 ? * 2,3,4,5,6 *)")

    def test_custom_timezone(self):
        rules = self.matcher.get_eventbridge_schedules(timezone_id="UTC")
        self.assertEqual(rules[0]["timezone"], "UTC")


if __name__ == "__main__":
    unittest.main()
