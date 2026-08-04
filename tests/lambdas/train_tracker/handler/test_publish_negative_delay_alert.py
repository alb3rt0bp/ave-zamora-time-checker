import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 10, tzinfo=TZ)


class TestPublishNegativeDelayAlert(HandlerTestCase):
    def test_publishes_expected_payload(self):
        self.handler._publish_negative_delay_alert("G100", "Galicia", -562, -20, NOW, SAMPLE_LOG_EXTRA)

        [alert] = self.get_published_data_quality_alerts()
        self.assertIn("G100", alert["subject"])
        self.assertIn("Galicia", alert["message"])
        self.assertIn("-562", alert["message"])
        self.assertIn("-20", alert["message"])
        self.assertIn(NOW.isoformat(), alert["message"])

    def test_does_not_publish_when_topic_not_configured(self):
        with patch.object(self.handler, "DATA_QUALITY_ALERT_SNS_TOPIC_ARN", ""):
            self.handler._publish_negative_delay_alert("G100", "Galicia", -562, -20, NOW, SAMPLE_LOG_EXTRA)

        self.assertEqual(self.get_published_data_quality_alerts(), [])

    def test_does_not_raise_when_sns_publish_fails(self):
        with patch.object(self.handler.sns, "publish", side_effect=Exception("boom")):
            self.handler._publish_negative_delay_alert("G100", "Galicia", -562, -20, NOW, SAMPLE_LOG_EXTRA)


if __name__ == "__main__":
    unittest.main()
