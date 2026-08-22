import json
import unittest
from datetime import datetime, timedelta, timezone

import boto3
from moto import mock_aws

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
import trends_reader


class TestGetTrendingHashtags(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.s3 = boto3.client("s3", region_name=tweet_notifier_env.AWS_REGION)
        self.s3.create_bucket(
            Bucket=trends_reader.DATALAKE_S3_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": tweet_notifier_env.AWS_REGION},
        )

    def _put_trends(self, hashtags, fetched_at):
        self.s3.put_object(
            Bucket=trends_reader.DATALAKE_S3_BUCKET,
            Key=trends_reader.TRENDS_S3_KEY,
            Body=json.dumps({"hashtags": hashtags, "fetched_at": fetched_at.isoformat()}).encode("utf-8"),
        )

    def test_returns_stored_hashtags(self):
        self._put_trends(["#Uno", "#Dos"], datetime.now(timezone.utc))

        result = trends_reader.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, ["#Uno", "#Dos"])

    def test_returns_empty_list_when_object_missing(self):
        result = trends_reader.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [])

    def test_returns_empty_list_when_trends_are_stale(self):
        stale_fetch = datetime.now(timezone.utc) - timedelta(hours=trends_reader.TRENDS_MAX_AGE_HOURS + 1)
        self._put_trends(["#Viejo"], stale_fetch)

        result = trends_reader.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [])

    def test_returns_stored_hashtags_when_just_within_max_age(self):
        fresh_fetch = datetime.now(timezone.utc) - timedelta(hours=trends_reader.TRENDS_MAX_AGE_HOURS - 1)
        self._put_trends(["#Reciente"], fresh_fetch)

        result = trends_reader.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, ["#Reciente"])

    def test_returns_empty_list_on_malformed_json(self):
        self.s3.put_object(
            Bucket=trends_reader.DATALAKE_S3_BUCKET,
            Key=trends_reader.TRENDS_S3_KEY,
            Body=b"not json",
        )

        result = trends_reader.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
