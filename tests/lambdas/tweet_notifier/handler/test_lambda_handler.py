import json
import unittest
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.dummies import tweet_notifier_env
from tests.dummies.fake_http import fake_urlopen_json

CREDENTIALS = {
    "consumer_key": "ck",
    "consumer_secret": "cs",
    "access_token": "at",
    "access_token_secret": "ats",
}

SNS_EVENT = {
    "Records": [
        {
            "Sns": {
                "Message": json.dumps({
                    "cod_comercial": "M100",
                    "sentido": "Madrid",
                    "hora_programada": "08:30",
                    "hora_llegada_corregida": "08:50",
                    "minutos_retraso": 20,
                    "fecha": "2026-07-31",
                })
            }
        }
    ]
}


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
            SecretString=json.dumps(CREDENTIALS),
        )

        self.module = tweet_notifier_env.import_tweet_notifier_handler()
        self.module._credentials_cache = None  # aislar la caché entre tests

    def test_posts_one_tweet_per_sns_record(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})
            result = self.module.lambda_handler(SNS_EVENT, FakeContext())

        self.assertEqual(result, {"statusCode": 200, "published": 1})
        mock_urlopen.assert_called_once()

    def test_tweet_text_includes_train_code_and_delay(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})
            self.module.lambda_handler(SNS_EVENT, FakeContext())

        sent_request = mock_urlopen.call_args[0][0]
        body = json.loads(sent_request.data.decode("utf-8"))
        self.assertIn("M100", body["text"])
        self.assertIn("20", body["text"])

    def test_reuses_cached_credentials_across_invocations(self):
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch.object(
                 self.module.secretsmanager, "get_secret_value",
                 wraps=self.module.secretsmanager.get_secret_value,
             ) as mock_get_secret:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})

            self.module.lambda_handler(SNS_EVENT, FakeContext())
            self.module.lambda_handler(SNS_EVENT, FakeContext())

            # La caché de módulo evita una segunda llamada a Secrets Manager.
            mock_get_secret.assert_called_once()


if __name__ == "__main__":
    unittest.main()
