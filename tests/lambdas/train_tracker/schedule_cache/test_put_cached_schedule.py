import json
import unittest
from datetime import date

import boto3
from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from schedule_cache import put_cached_schedule, get_cached_schedule

BUCKET = "test-put-cached-schedule-bucket"
DAY = date(2026, 1, 5)

TRAINS = [{"cod_comercial": "M100", "sentido": "Madrid"}]


class TestPutCachedSchedule(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.s3 = boto3.client("s3", region_name=aws_env.AWS_REGION)
        self.s3.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": aws_env.AWS_REGION}
        )

    def test_writes_object_readable_back_via_get_cached_schedule(self):
        put_cached_schedule(self.s3, BUCKET, DAY, TRAINS, SAMPLE_LOG_EXTRA)

        self.assertEqual(get_cached_schedule(self.s3, BUCKET, DAY, SAMPLE_LOG_EXTRA), TRAINS)

    def test_uses_the_expected_key(self):
        put_cached_schedule(self.s3, BUCKET, DAY, TRAINS, SAMPLE_LOG_EXTRA)

        obj = self.s3.get_object(Bucket=BUCKET, Key="schedules/2026-01-05.json")
        body = json.loads(obj["Body"].read())
        self.assertEqual(body["trains"], TRAINS)
        self.assertIn("generated_at", body)

    def test_does_not_raise_when_bucket_does_not_exist(self):
        # No relanza errores de S3: un fallo aquí no debe tirar el ciclo de
        # polling, solo hace que el próximo ciclo reintente la descarga.
        try:
            put_cached_schedule(self.s3, "nonexistent-bucket-xyz", DAY, TRAINS, SAMPLE_LOG_EXTRA)
        except Exception as exc:  # pragma: no cover - queremos que esto falle el test si ocurre
            self.fail(f"put_cached_schedule no debería relanzar excepciones de S3: {exc}")


if __name__ == "__main__":
    unittest.main()
