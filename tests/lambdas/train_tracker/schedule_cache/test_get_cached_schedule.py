import json
import unittest
from datetime import date

import boto3
from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from schedule_cache import get_cached_schedule

BUCKET = "test-get-cached-schedule-bucket"
DAY = date(2026, 1, 5)

TRAINS = [{"cod_comercial": "M100", "sentido": "Madrid"}]


class TestGetCachedSchedule(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.s3 = boto3.client("s3", region_name=aws_env.AWS_REGION)
        self.s3.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": aws_env.AWS_REGION}
        )

    def test_returns_none_when_key_does_not_exist(self):
        result = get_cached_schedule(self.s3, BUCKET, DAY, SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)

    def test_returns_trains_from_cached_object(self):
        self.s3.put_object(
            Bucket=BUCKET, Key="schedules/2026-01-05.json",
            Body=json.dumps({"generated_at": "2026-01-05T00:10:00+00:00", "trains": TRAINS}).encode("utf-8"),
        )

        result = get_cached_schedule(self.s3, BUCKET, DAY, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, TRAINS)

    def test_returns_none_for_corrupt_json(self):
        self.s3.put_object(Bucket=BUCKET, Key="schedules/2026-01-05.json", Body=b"not json")

        result = get_cached_schedule(self.s3, BUCKET, DAY, SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)

    def test_returns_none_when_trains_key_missing(self):
        self.s3.put_object(
            Bucket=BUCKET, Key="schedules/2026-01-05.json",
            Body=json.dumps({"generated_at": "2026-01-05T00:10:00+00:00"}).encode("utf-8"),
        )

        result = get_cached_schedule(self.s3, BUCKET, DAY, SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)

    def test_uses_a_different_key_per_date(self):
        self.s3.put_object(
            Bucket=BUCKET, Key="schedules/2026-01-05.json",
            Body=json.dumps({"trains": TRAINS}).encode("utf-8"),
        )

        result = get_cached_schedule(self.s3, BUCKET, date(2026, 1, 6), SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
