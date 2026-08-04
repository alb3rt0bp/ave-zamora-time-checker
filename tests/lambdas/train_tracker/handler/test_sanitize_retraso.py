import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 10, tzinfo=TZ)


class TestSanitizeRetraso(HandlerTestCase):
    def test_returns_unchanged_when_within_threshold(self):
        # NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES=-10 en el entorno de test: -10 no es anómalo.
        result = self.handler._sanitize_retraso("G100", "Galicia", -10, "08:30", NOW, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, -10)
        self.assertEqual(self.get_published_data_quality_alerts(), [])

    def test_returns_unchanged_for_positive_delay(self):
        result = self.handler._sanitize_retraso("G100", "Galicia", 20, "08:30", NOW, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, 20)
        self.assertEqual(self.get_published_data_quality_alerts(), [])

    def test_corrects_anomalous_negative_delay(self):
        # Bug real observado en la API de Renfe: ultRetraso=-562.
        result = self.handler._sanitize_retraso("G100", "Galicia", -562, "08:30", NOW, SAMPLE_LOG_EXTRA)

        # hora_referencia=08:30, now_local=08:10 -> el tren aún no ha llegado
        # a esa hora de referencia: retraso corregido = -20 min.
        self.assertEqual(result, -20)

    def test_publishes_data_quality_alert_on_anomaly(self):
        self.handler._sanitize_retraso("G100", "Galicia", -562, "08:30", NOW, SAMPLE_LOG_EXTRA)

        [alert] = self.get_published_data_quality_alerts()
        self.assertIn("G100", alert["subject"])
        self.assertIn("-562", alert["message"])
        self.assertIn("-20", alert["message"])

    def test_publishes_just_below_threshold(self):
        self.handler._sanitize_retraso("G100", "Galicia", -11, "08:30", NOW, SAMPLE_LOG_EXTRA)

        self.assertEqual(len(self.get_published_data_quality_alerts()), 1)


if __name__ == "__main__":
    unittest.main()
