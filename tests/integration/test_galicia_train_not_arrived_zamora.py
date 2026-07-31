"""
Escenario de integración: tren activo dirección Galicia que todavía no ha
llegado a Zamora.
"""
import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

G100_ANTES_DE_ZAMORA = {
    "codComercial": "G100",
    "codEstAnt": "10000",  # distinto de ZAMORA_CODE (30200)
    "codEstSig": "30200",
    "ultRetraso": 2,
}


class FakeContext:
    aws_request_id = "integration-galicia-not-arrived"


class TestGaliciaTrainNotArrivedZamora(HandlerTestCase):
    def test_updates_state_without_recording_anything(self):
        # G100: hora_salida 08:00, ventana activa desde las 07:00.
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 20))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([G100_ANTES_DE_ZAMORA])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["recorded"], 0)

        item = self.get_item("G100", "2026-01-05")
        self.assertIsNotNone(item)
        self.assertFalse(item["entregado"])
        self.assertNotIn("cod_est_ant", item)
        self.assertEqual(item["ult_retraso"], 2)

        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)


if __name__ == "__main__":
    unittest.main()
