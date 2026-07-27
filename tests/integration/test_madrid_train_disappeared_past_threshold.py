"""
Escenario de integración: tren activo dirección Madrid que ha desaparecido
de la flota tras haber sido visto (y haber pasado por Zamora), una vez
superado el umbral de hora_llegada_destino + retraso conocido.

Simula dos ciclos: se siembra en DynamoDB el estado que habría dejado un
ciclo anterior (visto, ya capturado en Zamora, con retraso conocido) y se
ejecuta lambda_handler para el ciclo en el que el tren ya no aparece en la
flota.
"""
import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc


class FakeContext:
    aws_request_id = "integration-madrid-disappeared"


class TestMadridTrainDisappearedPastThreshold(HandlerTestCase):
    def test_records_arrival_with_last_known_data(self):
        # Estado dejado por un ciclo anterior: visto, ya pasó por Zamora,
        # con 5 min de retraso conocido.
        self.table.put_item(Item={
            "pk": "M100#2026-01-05",
            "sk": "TRACKING",
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "08:30",
            "ult_retraso": 5,
            "cod_est_ant": "30200",
            "capturado_en_zamora": True,
            "done": False,
        })

        # Umbral de reintentos: 08:30 + 5 = 08:35. Ventana activa (matcher)
        # cierra a las 08:30 + 5 + 10 = 08:45. Usamos las 08:40, dentro de
        # ambos márgenes.
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 40))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([])  # M100 ya no aparece
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["recorded"], 1)

        item = self.get_item("M100", "2026-01-05")
        self.assertTrue(item["done"])

        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)["Contents"]
        self.assertEqual(len(objects), 1)
        self.assertIn("M100_Madrid", objects[0]["Key"])


if __name__ == "__main__":
    unittest.main()
