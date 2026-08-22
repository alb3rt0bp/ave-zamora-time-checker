import json
import unittest
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.dummies import trend_fetcher_env


class FakeContext:
    aws_request_id = "test-request-id"


class TestLambdaHandler(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.s3 = boto3.client("s3", region_name=trend_fetcher_env.AWS_REGION)
        self.s3.create_bucket(
            Bucket=trend_fetcher_env.DATALAKE_S3_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": trend_fetcher_env.AWS_REGION},
        )

        self.module = trend_fetcher_env.import_trend_fetcher_handler()

    def _get_stored_trends(self):
        obj = self.s3.get_object(
            Bucket=trend_fetcher_env.DATALAKE_S3_BUCKET, Key=trend_fetcher_env.TRENDS_S3_KEY
        )
        return json.loads(obj["Body"].read())

    def test_writes_fetched_hashtags_to_s3(self):
        with patch.object(
            self.module.xfetch_client, "get_trending_hashtags", return_value=["#Uno", "#Dos"]
        ):
            result = self.module.lambda_handler({}, FakeContext())

        self.assertEqual(result, {"statusCode": 200, "hashtags_count": 2})
        stored = self._get_stored_trends()
        self.assertEqual(stored["hashtags"], ["#Uno", "#Dos"])
        self.assertIn("fetched_at", stored)

    def test_writes_empty_list_when_xfetch_returns_nothing(self):
        with patch.object(self.module.xfetch_client, "get_trending_hashtags", return_value=[]):
            result = self.module.lambda_handler({}, FakeContext())

        self.assertEqual(result, {"statusCode": 200, "hashtags_count": 0})
        self.assertEqual(self._get_stored_trends()["hashtags"], [])


if __name__ == "__main__":
    unittest.main()
