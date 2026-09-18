import json
import unittest
from unittest.mock import patch

from tests.dummies import api_env
from tests.dummies.api_handler_test_case import ApiHandlerTestCase
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

TODAY_ISO = MONDAY.isoformat()
CACHE_KEY = f"schedules/reference-{TODAY_ISO}.json"

GTFS_TRAINS = [
    {
        "cod_comercial": "04154", "sentido": "Madrid",
        "hora_salida": "07:41", "hora_llegada_destino": "08:49",
        "weekdays": [0, 1, 2, 3, 4],
    },
]


class FakeContext:
    aws_request_id = "refresh-schedule-reference-test"


class TestRefreshScheduleReferenceHandler(ApiHandlerTestCase):
    def _frozen(self):
        return make_frozen_datetime(madrid_time_to_utc(MONDAY, 0, 5))

    def _call(self):
        with patch("api_handler.datetime", self._frozen()):
            return self.handler.refresh_schedule_reference_handler({}, FakeContext())

    @patch("api_handler.build_schedule_reference")
    @patch("api_handler.GtfsClient")
    def test_resolves_from_gtfs_and_caches_when_no_cache_exists(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {"trips.txt": "..."}
        mock_build.return_value = GTFS_TRAINS

        self._call()

        cached = self.s3.get_object(Bucket=api_env.S3_BUCKET_NAME, Key=CACHE_KEY)
        self.assertEqual(json.loads(cached["Body"].read())["trains"], GTFS_TRAINS)

    @patch("api_handler.build_schedule_reference")
    @patch("api_handler.GtfsClient")
    def test_does_not_call_gtfs_when_already_cached(self, mock_gtfs_client_cls, mock_build):
        self.s3.put_object(
            Bucket=api_env.S3_BUCKET_NAME, Key=CACHE_KEY,
            Body=json.dumps({"trains": GTFS_TRAINS}).encode("utf-8"),
        )

        self._call()

        mock_gtfs_client_cls.assert_not_called()
        mock_build.assert_not_called()

    @patch("api_handler.GtfsClient")
    def test_gtfs_failure_does_not_raise_and_leaves_cache_empty(self, mock_gtfs_client_cls):
        mock_gtfs_client_cls.return_value.download_and_extract.side_effect = RuntimeError("boom")

        self._call()  # no debe lanzar

        with self.assertRaises(self.s3.exceptions.NoSuchKey):
            self.s3.get_object(Bucket=api_env.S3_BUCKET_NAME, Key=CACHE_KEY)

    @patch("api_handler.build_schedule_reference", return_value=[])
    @patch("api_handler.GtfsClient")
    def test_empty_gtfs_result_does_not_raise_and_leaves_cache_empty(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {}

        self._call()  # no debe lanzar

        with self.assertRaises(self.s3.exceptions.NoSuchKey):
            self.s3.get_object(Bucket=api_env.S3_BUCKET_NAME, Key=CACHE_KEY)


if __name__ == "__main__":
    unittest.main()
