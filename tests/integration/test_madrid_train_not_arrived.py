"""
Escenario de integración: tren activo dirección Madrid que ya ha pasado por
Zamora pero todavía no ha llegado a Madrid Chamartín (sigue en ruta).
"""
import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

M100_TRAS_ZAMORA = {
    "codComercial": "M100",
    "codEstAnt": "30200",  # ZAMORA_CODE: ya pasó por Zamora
    "codEstSig": "40000",
    "ultRetraso": 5,
}


class FakeContext:
    aws_request_id = "integration-madrid-not-arrived"


class TestMadridTrainNotArrived(HandlerTestCase):
    def test_marks_captured_in_zamora_without_recording_arrival(self):
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 0))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([M100_TRAS_ZAMORA])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["recorded"], 0)

        item = self.get_item("M100", "2026-01-05")
        self.assertIsNotNone(item)
        self.assertFalse(item["entregado"])
        self.assertTrue(item["capturado_en_zamora"])
        self.assertEqual(item["ult_retraso"], 5)
        # M100: hora_salida (paso programado por Zamora) 07:00 + ultRetraso 5.
        self.assertEqual(item["hora_paso_zamora"], "07:05")

        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)


if __name__ == "__main__":
    unittest.main()
