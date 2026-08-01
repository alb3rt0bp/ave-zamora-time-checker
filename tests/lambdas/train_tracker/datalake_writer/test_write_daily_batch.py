import json
import unittest
from datetime import date

import boto3
from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from datalake_writer import DatalakeWriter

BUCKET = "test-write-daily-batch-bucket"
DAY = date(2026, 1, 5)

RECORDS = [
    {"event_id": "M100-2026-01-05T08:30", "cod_comercial": "M100", "sentido": "Madrid",
     "tipo_dia": "laborable", "dia_semana": "Monday", "hora_programada": "08:30",
     "hora_llegada_corregida": "08:35", "minutos_retraso": 5},
    {"event_id": "G100-2026-01-05T09:30", "cod_comercial": "G100", "sentido": "Galicia",
     "tipo_dia": "laborable", "dia_semana": "Monday", "hora_programada": "09:30",
     "hora_llegada_corregida": "09:30", "minutos_retraso": 0},
]


class TestWriteDailyBatch(unittest.TestCase):
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

    def test_writes_single_object_with_expected_key(self):
        key = self.writer.write_daily_batch(RECORDS, DAY)

        self.assertEqual(key, "zamora-trains/year=2026/month=01/day=05/2026-01-05.jsonl")
        listed = self.s3.list_objects_v2(Bucket=BUCKET)["Contents"]
        self.assertEqual(len(listed), 1)

    def test_writes_one_json_object_per_line(self):
        key = self.writer.write_daily_batch(RECORDS, DAY)

        body = self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8")
        lines = body.splitlines()
        self.assertEqual(len(lines), 2)
        parsed = [json.loads(line) for line in lines]
        self.assertEqual(parsed[0]["cod_comercial"], "M100")
        self.assertEqual(parsed[1]["cod_comercial"], "G100")

    def test_content_type_is_ndjson(self):
        key = self.writer.write_daily_batch(RECORDS, DAY)

        content_type = self.s3.get_object(Bucket=BUCKET, Key=key)["ContentType"]
        self.assertEqual(content_type, "application/x-ndjson")


if __name__ == "__main__":
    unittest.main()
