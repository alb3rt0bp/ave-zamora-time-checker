"""
Escenario de integración: tren activo dirección Galicia que acaba de pasar
por Zamora. Cubre el ciclo completo del nuevo enfoque: el polling solo marca
'entregado' en DynamoDB (sin escribir a S3), y el volcado diario del día
siguiente es quien produce el único fichero JSONL en S3.
"""
import json
import unittest
from datetime import timedelta
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
    def test_polling_marks_entregado_without_writing_to_s3(self):
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 20))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([G100_EN_ZAMORA])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["recorded"], 1)

        item = self.get_item("G100", "2026-01-05")
        self.assertTrue(item["entregado"])
        self.assertTrue(item["capturado_en_zamora"])
        self.assertIn("hora_llegada_corregida", item)
        # Sentido Galicia: hora_paso_zamora coincide con hora_llegada_corregida
        # (mismo evento). G100: hora_llegada_destino 09:30 + ultRetraso 4.
        self.assertEqual(item["hora_paso_zamora"], "09:34")
        self.assertEqual(item["hora_paso_zamora"], item["hora_llegada_corregida"])

        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)

    def test_daily_dump_next_day_writes_the_captured_train(self):
        frozen_poll = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 20))
        with patch("handler.datetime", frozen_poll), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([G100_EN_ZAMORA])
            self.handler.lambda_handler({}, FakeContext())

        next_day = MONDAY + timedelta(days=1)
        frozen_dump = make_frozen_datetime(madrid_time_to_utc(next_day, 0, 15))
        with patch("handler.datetime", frozen_dump):
            dump_result = self.handler.daily_dump_handler({}, FakeContext())

        # El fixture siembra M100 (Madrid) y G100 (Galicia) para el lunes.
        # Solo G100 se capturó en este escenario; M100 se vuelca igualmente,
        # pero como cancelado (nunca visto en flotaLD.json en todo el día).
        self.assertEqual(dump_result["written"], 2)
        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=dump_result["key"])["Body"].read()
        records = {r["cod_comercial"]: r for r in
                   (json.loads(line) for line in body.decode("utf-8").splitlines())}

        record = records["G100"]
        self.assertEqual(record["sentido"], "Galicia")
        self.assertEqual(record["minutos_retraso"], 4)
        self.assertEqual(record["hora_paso_zamora"], "09:34")
        self.assertFalse(record["cancelado"])
        self.assertNotIn("capturado_en_zamora", record)
        self.assertNotIn("cod_est_ant", record)

        cancelled = records["M100"]
        self.assertTrue(cancelled["cancelado"])
        self.assertIsNone(cancelled["minutos_retraso"])


if __name__ == "__main__":
    unittest.main()
