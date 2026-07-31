"""
Escenario de integración: no hay ningún tren activo en el ciclo.
Se ejecuta lambda_handler de punta a punta con AWS mockeado (moto) y sin
llegar a llamar a la API de Renfe (no debería hacer falta). El sembrado de
trenes de hoy (_seed_todays_trains) sí ocurre, independientemente de si hay
trenes activos o no: por eso hay actividad en DynamoDB aunque no en S3.
"""
import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc


class FakeContext:
    aws_request_id = "integration-no-active-trains"


class TestNoActiveTrains(HandlerTestCase):
    def test_no_active_trains_skips_renfe_and_s3_but_seeds_dynamodb(self):
        # 05:00 es anterior a la ventana de cualquier tren del fixture
        # (el más temprano, M100, abre a las 06:00).
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 5, 0))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result, {"statusCode": 200, "active": 0, "recorded": 0})
        mock_urlopen.assert_not_called()

        # El sembrado del día sí ha creado placeholders (M100, G100 hoy).
        self.assertIsNotNone(self.get_item("M100", "2026-01-05"))
        self.assertIsNotNone(self.get_item("G100", "2026-01-05"))

        # Pero nunca se escribe a S3 durante el polling.
        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)


if __name__ == "__main__":
    unittest.main()
