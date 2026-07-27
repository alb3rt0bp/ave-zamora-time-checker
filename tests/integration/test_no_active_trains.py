"""
Escenario de integración: no hay ningún tren activo en el ciclo.
Se ejecuta lambda_handler de punta a punta con AWS mockeado (moto) y sin
llegar a llamar a la API de Renfe (no debería hacer falta).
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
    def test_no_active_trains_produces_no_side_effects(self):
        # 05:00 es anterior a la ventana de cualquier tren del fixture
        # (el más temprano, M100, abre a las 06:00).
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 5, 0))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result, {"statusCode": 200, "active": 0, "recorded": 0})
        mock_urlopen.assert_not_called()

        # Ni rastro en DynamoDB ni en S3.
        scan = self.table.scan()
        self.assertEqual(scan["Items"], [])
        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)


if __name__ == "__main__":
    unittest.main()
