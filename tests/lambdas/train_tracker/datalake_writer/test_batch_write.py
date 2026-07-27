import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from datalake_writer import DatalakeWriter

BUCKET = "test-batch-write-bucket"
TS = datetime(2026, 1, 5, 7, 41, 0, tzinfo=ZoneInfo("Europe/Madrid"))


class TestBatchWrite(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.s3 = boto3.client("s3", region_name=aws_env.AWS_REGION)
        self.s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": aws_env.AWS_REGION},
        )
        self.writer = DatalakeWriter(self.s3, BUCKET, SAMPLE_LOG_EXTRA)

    def test_writes_all_records_and_returns_all_keys(self):
        records = [
            {"cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable"},
            {"cod_comercial": "G100", "sentido": "Galicia", "tipo_dia": "laborable"},
        ]

        keys = self.writer.batch_write(records, TS)

        self.assertEqual(len(keys), 2)
        listed = self.s3.list_objects_v2(Bucket=BUCKET)["Contents"]
        self.assertEqual(len(listed), 2)

    def test_continues_after_one_record_fails(self):
        records = [
            {"cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable"},
            {"sentido": "Galicia"},  # sin cod_comercial → KeyError al construir la key
            {"cod_comercial": "G100", "sentido": "Galicia", "tipo_dia": "laborable"},
        ]

        keys = self.writer.batch_write(records, TS)

        self.assertEqual(len(keys), 2)


if __name__ == "__main__":
    unittest.main()
