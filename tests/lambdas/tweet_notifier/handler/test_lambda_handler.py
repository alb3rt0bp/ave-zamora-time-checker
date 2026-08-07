import json
import unittest
from unittest.mock import patch

from tests.dummies import tweet_notifier_env
import claude_client

ALERT_PAYLOAD = {
    "cod_comercial": "M100",
    "sentido": "Madrid",
    "hora_programada": "08:30",
    "hora_llegada_corregida": "08:50",
    "minutos_retraso": 20,
    "fecha": "2026-07-31",
    "es_tren_madrugador": False,
}


def _sns_event(*payloads):
    return {"Records": [{"Sns": {"Message": json.dumps(p)}} for p in payloads]}


class FakeContext:
    aws_request_id = "test-request-id"


class TestLambdaHandler(unittest.TestCase):
    def setUp(self):
        self.module = tweet_notifier_env.import_tweet_notifier_handler()

    def test_drafts_and_logs_one_tweet_per_sns_record(self):
        with patch.object(
            claude_client, "draft_tweet",
            return_value={"tweet_text": "texto", "hashtags": ["#ZamoraNecesitaTren"]},
        ) as mock_draft:
            result = self.module.lambda_handler(_sns_event(ALERT_PAYLOAD), FakeContext())

        self.assertEqual(result, {"statusCode": 200, "published": 1})
        mock_draft.assert_called_once()

    def test_one_failed_record_does_not_interrupt_the_batch(self):
        ok_alert = {**ALERT_PAYLOAD, "cod_comercial": "M200"}
        with patch.object(
            claude_client, "draft_tweet",
            side_effect=[
                RuntimeError("Claude no ha podido redactar"),
                {"tweet_text": "texto", "hashtags": ["#ZamoraNecesitaTren"]},
            ],
        ) as mock_draft:
            result = self.module.lambda_handler(_sns_event(ALERT_PAYLOAD, ok_alert), FakeContext())

        self.assertEqual(result, {"statusCode": 200, "published": 1})
        self.assertEqual(mock_draft.call_count, 2)

    def test_does_not_publish_to_x(self):
        # Modo dry-run: client.post_tweet sigue comentado en el handler real.
        with patch.object(
            claude_client, "draft_tweet",
            return_value={"tweet_text": "texto", "hashtags": ["#ZamoraNecesitaTren"]},
        ), patch("urllib.request.urlopen") as mock_urlopen:
            self.module.lambda_handler(_sns_event(ALERT_PAYLOAD), FakeContext())

        mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
