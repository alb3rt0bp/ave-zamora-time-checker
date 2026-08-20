import unittest

import boto3
from moto import mock_aws

from tests.dummies import tweet_notifier_env
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA


class TestGetCredentials(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.secretsmanager = boto3.client("secretsmanager", region_name=tweet_notifier_env.AWS_REGION)
        self.secretsmanager.create_secret(
            Name=tweet_notifier_env.X_API_CREDENTIALS_SECRET_ARN,
            SecretString='{"consumer_key": "ck", "consumer_secret": "cs", '
                         '"access_token": "at", "access_token_secret": "ats"}',
        )

        self.module = tweet_notifier_env.import_tweet_notifier_handler()
        self.module._credentials_cache = None

    def test_reads_credentials_from_secrets_manager(self):
        credentials = self.module._get_credentials(SAMPLE_LOG_EXTRA)

        self.assertEqual(credentials, {
            "consumer_key": "ck", "consumer_secret": "cs",
            "access_token": "at", "access_token_secret": "ats",
        })

    def test_caches_credentials_across_calls(self):
        first = self.module._get_credentials(SAMPLE_LOG_EXTRA)
        self.secretsmanager.put_secret_value(
            SecretId=tweet_notifier_env.X_API_CREDENTIALS_SECRET_ARN,
            SecretString='{"consumer_key": "changed"}',
        )

        second = self.module._get_credentials(SAMPLE_LOG_EXTRA)

        self.assertIs(second, first)
        self.assertEqual(second["consumer_key"], "ck")


if __name__ == "__main__":
    unittest.main()
