import json
import unittest
from datetime import date
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from schedule_resolver import resolve_todays_schedule

BUCKET = "test-schedule-resolver-bucket"
DAY = date(2026, 1, 5)  # MONDAY (ver tests/dummies/reference_dates.py) → laborable

STATIC_FALLBACK = {
    "polling_window_minutes": 30,
    "trains": [
        {
            "cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable",
            "hora_salida": "07:00", "hora_llegada_destino": "08:30",
        },
        {
            "cod_comercial": "M200", "sentido": "Madrid", "tipo_dia": "domingo",
            "hora_salida": "09:00", "hora_llegada_destino": "10:15",
        },
    ],
}

GTFS_TRAINS = [
    {
        "cod_comercial": "04154", "sentido": "Madrid", "tipo_dia": "laborable",
        "hora_salida": "07:41", "hora_llegada_destino": "08:49",
    },
]


class TestResolveTodaysSchedule(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.s3 = boto3.client("s3", region_name=aws_env.AWS_REGION)
        self.s3.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": aws_env.AWS_REGION}
        )
        self.alerts: list[str] = []

    def _resolve(self):
        return resolve_todays_schedule(
            self.s3, BUCKET, DAY, "30200", "17000", STATIC_FALLBACK, self.alerts.append, SAMPLE_LOG_EXTRA
        )

    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", False)
    def test_flag_disabled_returns_filtered_static_fallback(self):
        result = self._resolve()

        self.assertEqual([t["cod_comercial"] for t in result["trains"]], ["M100"])
        self.assertEqual(result["polling_window_minutes"], 30)
        self.assertEqual(self.alerts, [])

    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    @patch("schedule_resolver.build_todays_trains")
    @patch("schedule_resolver.GtfsClient")
    def test_downloads_from_gtfs_and_caches_when_no_cache_exists(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {"trips.txt": "..."}
        mock_build.return_value = GTFS_TRAINS

        result = self._resolve()

        self.assertEqual(result["trains"], GTFS_TRAINS)
        cached = self.s3.get_object(Bucket=BUCKET, Key="schedules/2026-01-05.json")
        self.assertEqual(json.loads(cached["Body"].read())["trains"], GTFS_TRAINS)
        self.assertEqual(self.alerts, [])

    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    @patch("schedule_resolver.build_todays_trains")
    @patch("schedule_resolver.GtfsClient")
    def test_uses_existing_cache_without_calling_gtfs(self, mock_gtfs_client_cls, mock_build):
        self.s3.put_object(
            Bucket=BUCKET, Key="schedules/2026-01-05.json",
            Body=json.dumps({"trains": GTFS_TRAINS}).encode("utf-8"),
        )

        result = self._resolve()

        self.assertEqual(result["trains"], GTFS_TRAINS)
        mock_gtfs_client_cls.assert_not_called()
        mock_build.assert_not_called()

    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    @patch("schedule_resolver.GtfsClient")
    def test_download_failure_falls_back_to_static_and_alerts(self, mock_gtfs_client_cls):
        mock_gtfs_client_cls.return_value.download_and_extract.side_effect = RuntimeError("boom")

        result = self._resolve()

        self.assertEqual([t["cod_comercial"] for t in result["trains"]], ["M100"])
        self.assertEqual(len(self.alerts), 1)
        self.assertIn("2026-01-05", self.alerts[0])

    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    @patch("schedule_resolver.build_todays_trains", return_value=[])
    @patch("schedule_resolver.GtfsClient")
    def test_empty_gtfs_result_falls_back_to_static_and_alerts(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {}

        result = self._resolve()

        self.assertEqual([t["cod_comercial"] for t in result["trains"]], ["M100"])
        self.assertEqual(len(self.alerts), 1)

    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    @patch("schedule_resolver.build_todays_trains", return_value=[])
    @patch("schedule_resolver.GtfsClient")
    def test_empty_gtfs_result_does_not_cache_the_empty_list(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {}

        self._resolve()

        with self.assertRaises(self.s3.exceptions.NoSuchKey):
            self.s3.get_object(Bucket=BUCKET, Key="schedules/2026-01-05.json")


if __name__ == "__main__":
    unittest.main()
