"""
Escenario de integración: tren activo dirección Galicia que acaba de pasar
por Zamora.
"""
import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

G100_EN_ZAMORA = {
    "codComercial": "G100",
    "codEstAnt": "30200",  # ZAMORA_CODE
    "codEstSig": "40000",
    "ultRetraso": 4,
}


class FakeContext:
    aws_request_id = "integration-galicia-passed-zamora"


class TestGaliciaTrainPassedZamora(HandlerTestCase):
    def test_records_passage_and_marks_done(self):
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 20))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([G100_EN_ZAMORA])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["recorded"], 1)

        item = self.get_item("G100", "2026-01-05")
        self.assertTrue(item["done"])
        self.assertTrue(item["capturado_en_zamora"])
        self.assertIn("hora_llegada_real", item)

        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)["Contents"]
        self.assertEqual(len(objects), 1)
        self.assertIn("G100_Galicia", objects[0]["Key"])

        import json
        body = json.loads(self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=objects[0]["Key"])["Body"].read())
        self.assertTrue(body["capturado_en_zamora"])
        self.assertEqual(body["cod_comercial"], "G100")
        self.assertEqual(body["sentido"], "Galicia")


if __name__ == "__main__":
    unittest.main()
