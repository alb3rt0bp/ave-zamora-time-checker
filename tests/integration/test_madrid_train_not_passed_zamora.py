"""
Escenario de integración: tren activo dirección Madrid que todavía no ha
pasado por Zamora (última estación conocida distinta de ZAMORA_CODE).
"""
import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

M100_ANTES_DE_ZAMORA = {
    "codComercial": "M100",
    "codEstAnt": "10000",  # ni ZAMORA_CODE (30200) ni CHAMARTIN_CODE (17000)
    "codEstSig": "20000",
    "ultRetraso": 3,
}


class FakeContext:
    aws_request_id = "integration-madrid-not-passed-zamora"


class TestMadridTrainNotPassedZamora(HandlerTestCase):
    def test_updates_state_without_recording_anything(self):
        # M100: hora_salida 07:00, ventana activa desde las 06:00.
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 7, 30))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([M100_ANTES_DE_ZAMORA])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["recorded"], 0)

        item = self.get_item("M100", "2026-01-05")
        self.assertIsNotNone(item)
        self.assertFalse(item["done"])
        self.assertFalse(item["capturado_en_zamora"])
        self.assertEqual(item["cod_est_ant"], "10000")
        self.assertEqual(item["ult_retraso"], 3)

        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)


if __name__ == "__main__":
    unittest.main()
