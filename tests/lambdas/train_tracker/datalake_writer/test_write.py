import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from datalake_writer import DatalakeWriter

BUCKET = "test-write-bucket"
TS = datetime(2026, 1, 5, 7, 41, 0, tzinfo=ZoneInfo("Europe/Madrid"))


class TestWrite(unittest.TestCase):
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

    def test_writes_object_with_expected_key(self):
        record = {
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "minutos_retraso": 5,
        }

        key = self.writer.write(record, TS)

        self.assertEqual(
            key, "zamora-trains/year=2026/month=01/day=05/M100_Madrid_20260105T074100.json"
        )
        body = self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        self.assertEqual(json.loads(body), record)

    def test_sets_metadata(self):
        record = {
            "cod_comercial": "G100",
            "sentido": "Galicia",
            "tipo_dia": "domingo",
            "minutos_retraso": 12,
        }

        key = self.writer.write(record, TS)

        metadata = self.s3.get_object(Bucket=BUCKET, Key=key)["Metadata"]
        self.assertEqual(metadata["cod-comercial"], "G100")
        self.assertEqual(metadata["sentido"], "Galicia")
        self.assertEqual(metadata["tipo-dia"], "domingo")
        self.assertEqual(metadata["retraso-min"], "12")

    def test_missing_minutos_retraso_defaults_metadata_to_zero(self):
        record = {"cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable"}

        key = self.writer.write(record, TS)

        metadata = self.s3.get_object(Bucket=BUCKET, Key=key)["Metadata"]
        self.assertEqual(metadata["retraso-min"], "0")


if __name__ == "__main__":
    unittest.main()
