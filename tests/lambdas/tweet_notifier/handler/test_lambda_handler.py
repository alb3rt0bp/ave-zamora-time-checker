import json
import unittest
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.dummies import tweet_notifier_env
from tests.dummies.fake_http import fake_urlopen_json
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
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        secretsmanager = boto3.client("secretsmanager", region_name=tweet_notifier_env.AWS_REGION)
        secretsmanager.create_secret(
            Name=tweet_notifier_env.X_API_CREDENTIALS_SECRET_ARN,
            SecretString='{"consumer_key": "ck", "consumer_secret": "cs", '
                         '"access_token": "at", "access_token_secret": "ats"}',
        )

        self.module = tweet_notifier_env.import_tweet_notifier_handler()
        self.module._credentials_cache = None

    def test_drafts_and_publishes_one_tweet_per_sns_record(self):
        with patch.object(
            claude_client, "draft_tweet",
            return_value={"tweet_text": "texto", "hashtags": ["#ZamoraNecesitaTren"]},
        ) as mock_draft, patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})
            result = self.module.lambda_handler(_sns_event(ALERT_PAYLOAD), FakeContext())

        self.assertEqual(result, {"statusCode": 200, "published": 1})
        mock_draft.assert_called_once()
        mock_urlopen.assert_called_once()

    def test_one_failed_record_does_not_interrupt_the_batch(self):
        ok_alert = {**ALERT_PAYLOAD, "cod_comercial": "M200"}
        with patch.object(
            claude_client, "draft_tweet",
            side_effect=[
                RuntimeError("Claude no ha podido redactar"),
                {"tweet_text": "texto", "hashtags": ["#ZamoraNecesitaTren"]},
            ],
        ) as mock_draft, patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})
            result = self.module.lambda_handler(_sns_event(ALERT_PAYLOAD, ok_alert), FakeContext())

        self.assertEqual(result, {"statusCode": 200, "published": 1})
        self.assertEqual(mock_draft.call_count, 2)

    def test_refines_and_publishes_tweet_that_first_exceeds_280_characters(self):
        long_text = "x" * 275
        short_text = "texto corto"
        with patch.object(
            claude_client, "draft_tweet",
            return_value={"tweet_text": long_text, "hashtags": ["#ZamoraNecesitaTren"]},
        ), patch.object(
            claude_client, "refine_tweet",
            return_value={"tweet_text": short_text, "hashtags": ["#ZamoraNecesitaTren"]},
        ) as mock_refine, patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})
            result = self.module.lambda_handler(_sns_event(ALERT_PAYLOAD), FakeContext())

        mock_refine.assert_called_once()
        self.assertEqual(result, {"statusCode": 200, "published": 1})
        sent_body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertIn(short_text, sent_body["text"])

    def test_warns_and_skips_publishing_when_still_over_280_after_refining(self):
        long_text = "x" * 275
        with self.assertLogs("tweet_notifier", level="WARNING") as logs, patch.object(
            claude_client, "draft_tweet",
            return_value={"tweet_text": long_text, "hashtags": ["#ZamoraNecesitaTren"]},
        ), patch.object(
            claude_client, "refine_tweet",
            return_value={"tweet_text": long_text, "hashtags": ["#ZamoraNecesitaTren"]},
        ), patch("urllib.request.urlopen") as mock_urlopen:
            result = self.module.lambda_handler(_sns_event(ALERT_PAYLOAD), FakeContext())

        self.assertEqual(result, {"statusCode": 200, "published": 0})
        self.assertTrue(any(
            "sigue superando los 280 caracteres" in message and long_text in message
            for message in logs.output
        ))
        mock_urlopen.assert_not_called()

    def test_warns_and_skips_publishing_when_refine_itself_fails(self):
        long_text = "x" * 275
        with self.assertLogs("tweet_notifier", level="WARNING") as logs, patch.object(
            claude_client, "draft_tweet",
            return_value={"tweet_text": long_text, "hashtags": ["#ZamoraNecesitaTren"]},
        ), patch.object(
            claude_client, "refine_tweet",
            side_effect=RuntimeError("Claude no ha podido redactar"),
        ), patch("urllib.request.urlopen") as mock_urlopen:
            result = self.module.lambda_handler(_sns_event(ALERT_PAYLOAD), FakeContext())

        self.assertEqual(result, {"statusCode": 200, "published": 0})
        self.assertTrue(any("sigue superando los 280 caracteres" in message for message in logs.output))
        mock_urlopen.assert_not_called()

    def test_does_not_refine_tweet_within_280_characters(self):
        with patch.object(
            claude_client, "draft_tweet",
            return_value={"tweet_text": "texto", "hashtags": ["#ZamoraNecesitaTren"]},
        ), patch.object(claude_client, "refine_tweet") as mock_refine, patch(
            "urllib.request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})
            self.module.lambda_handler(_sns_event(ALERT_PAYLOAD), FakeContext())

        mock_refine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
