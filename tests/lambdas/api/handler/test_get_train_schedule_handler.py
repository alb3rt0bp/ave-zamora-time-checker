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
    aws_request_id = "get-train-schedule-test"


class TestGetTrainScheduleHandler(ApiHandlerTestCase):
    def _frozen(self):
        return make_frozen_datetime(madrid_time_to_utc(MONDAY, 10, 0))

    def _call(self):
        with patch("api_handler.datetime", self._frozen()):
            return self.handler.get_train_schedule_handler({}, FakeContext())

    @patch("api_handler.build_schedule_reference")
    @patch("api_handler.GtfsClient")
    def test_resolves_from_gtfs_and_caches_when_no_cache_exists(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {"trips.txt": "..."}
        mock_build.return_value = GTFS_TRAINS

        response = self._call()

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), GTFS_TRAINS)

        cached = self.s3.get_object(Bucket=api_env.S3_BUCKET_NAME, Key=CACHE_KEY)
        self.assertEqual(json.loads(cached["Body"].read())["trains"], GTFS_TRAINS)

    @patch("api_handler.build_schedule_reference")
    @patch("api_handler.GtfsClient")
    def test_uses_existing_cache_without_calling_gtfs(self, mock_gtfs_client_cls, mock_build):
        self.s3.put_object(
            Bucket=api_env.S3_BUCKET_NAME, Key=CACHE_KEY,
            Body=json.dumps({"trains": GTFS_TRAINS}).encode("utf-8"),
        )

        response = self._call()

        self.assertEqual(json.loads(response["body"]), GTFS_TRAINS)
        mock_gtfs_client_cls.assert_not_called()
        mock_build.assert_not_called()

    @patch("api_handler.GtfsClient")
    def test_gtfs_download_failure_falls_back_to_static_fixture(self, mock_gtfs_client_cls):
        mock_gtfs_client_cls.return_value.download_and_extract.side_effect = RuntimeError("boom")

        response = self._call()

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        by_cod = {t["cod_comercial"]: t for t in body}
        # tests/dummies/train_schedules_sample.json: M100/G100 (laborable), M200/G200 (domingo).
        self.assertEqual(set(by_cod), {"M100", "G100", "M200", "G200"})
        self.assertEqual(by_cod["M100"]["hora_salida"], "07:00")
        self.assertEqual([t["cod_comercial"] for t in body], sorted(t["cod_comercial"] for t in body))

    @patch("api_handler.build_schedule_reference", return_value=[])
    @patch("api_handler.GtfsClient")
    def test_empty_gtfs_result_falls_back_to_static_fixture(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {}

        response = self._call()

        by_cod = {t["cod_comercial"]: t for t in json.loads(response["body"])}
        self.assertEqual(set(by_cod), {"M100", "G100", "M200", "G200"})

    @patch("api_handler.build_schedule_reference", return_value=[])
    @patch("api_handler.GtfsClient")
    def test_empty_gtfs_result_does_not_cache_the_empty_list(self, mock_gtfs_client_cls, mock_build):
        mock_gtfs_client_cls.return_value.download_and_extract.return_value = {}

        self._call()

        with self.assertRaises(self.s3.exceptions.NoSuchKey):
            self.s3.get_object(Bucket=api_env.S3_BUCKET_NAME, Key=CACHE_KEY)

    def test_union_of_weekdays_across_multiple_schedule_rows(self):
        # _build_train_schedule_index es una función pura del fallback
        # estático: se prueba directamente con datos sintéticos (un tren con
        # una fila laborable y otra domingo), sin depender de GTFS ni de
        # SCHEDULES_FILE.
        trains = [
            {
                "cod_comercial": "X1",
                "sentido": "Madrid",
                "tipo_dia": "laborable",
                "weekdays": [0, 1, 2, 3, 4],
                "hora_salida": "07:41",
                "hora_llegada_destino": "09:10",
            },
            {
                "cod_comercial": "X1",
                "sentido": "Madrid",
                "tipo_dia": "domingo",
                "weekdays": [6],
                "hora_salida": "07:41",
                "hora_llegada_destino": "09:10",
            },
        ]

        index = self.handler._build_train_schedule_index(trains)

        self.assertEqual(
            index,
            [
                {
                    "cod_comercial": "X1",
                    "sentido": "Madrid",
                    "hora_salida": "07:41",
                    "hora_llegada_destino": "09:10",
                    "weekdays": [0, 1, 2, 3, 4, 6],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
