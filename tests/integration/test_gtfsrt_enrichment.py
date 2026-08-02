"""
Escenario de integración para el enriquecimiento aditivo con GTFS-RT (ver
CLAUDE.md, "Additional real-time source: GTFS-RT TripUpdates"). Cubre:
  1. Camino feliz: los campos *_gtfsrt llegan hasta el JSONL final.
  2. El fetch de trip_updates_LD.json falla y aun así el resto del pipeline
     (entregado, hora_llegada_corregida, minutos_retraso...) funciona
     exactamente igual que sin el enriquecimiento — la prueba de que
     "nunca bloquea el flujo principal" es un hecho, no solo una intención.
"""
import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json, fake_urlopen_by_url, raise_url_error
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc
from tests.dummies.gtfsrt_samples import ENTITY_G100

G100_EN_ZAMORA = {
    "codComercial": "G100",
    "codEstAnt": "30200",  # ZAMORA_CODE
    "codEstSig": "40000",
    "ultRetraso": 4,
}


class FakeContext:
    aws_request_id = "integration-gtfsrt-enrichment"


class TestGtfsrtEnrichmentHappyPath(HandlerTestCase):
    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    def test_gtfsrt_fields_flow_through_to_dynamo_and_jsonl(self):
        frozen_poll = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 20))
        with patch("handler.datetime", frozen_poll), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = fake_urlopen_by_url({
                "flotaLD.json": [G100_EN_ZAMORA],
                "trip_updates_LD.json": {"entity": [ENTITY_G100]},
            })
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["recorded"], 1)
        item = self.get_item("G100", "2026-01-05")
        # Campo ya existente (flotaLD.json): hora_llegada_destino 09:30 + ultRetraso 4.
        self.assertEqual(item["hora_llegada_corregida"], "09:34")
        # Campos nuevos (GTFS-RT): independientes del anterior, vienen de
        # ENTITY_G100 (delay=0, epoch → 08:34 Europe/Madrid).
        self.assertEqual(item["minutos_retraso_gtfsrt"], 0)
        self.assertEqual(item["hora_llegada_gtfsrt"], "08:34")
        self.assertEqual(item["hora_paso_zamora_gtfsrt"], "08:34")

        next_day = MONDAY + timedelta(days=1)
        frozen_dump = make_frozen_datetime(madrid_time_to_utc(next_day, 0, 15))
        with patch("handler.datetime", frozen_dump):
            dump_result = self.handler.daily_dump_handler({}, FakeContext())

        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=dump_result["key"])["Body"].read()
        records = {r["cod_comercial"]: r for r in
                   (json.loads(line) for line in body.decode("utf-8").splitlines())}
        record = records["G100"]
        self.assertEqual(record["minutos_retraso_gtfsrt"], 0)
        self.assertEqual(record["hora_llegada_gtfsrt"], "08:34")
        self.assertEqual(record["hora_paso_zamora_gtfsrt"], "08:34")


class TestGtfsrtEnrichmentFailureIsolation(HandlerTestCase):
    @patch("handler.GTFS_RT_ENRICHMENT_ENABLED", True)
    def test_gtfsrt_fetch_failure_does_not_block_primary_capture(self):
        frozen_poll = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 20))

        def urlopen_side_effect(req, timeout=None):
            if "flotaLD.json" in req.full_url:
                return fake_urlopen_json([G100_EN_ZAMORA])
            if "trip_updates_LD.json" in req.full_url:
                return raise_url_error()
            raise AssertionError(f"URL inesperada: {req.full_url}")

        with patch("handler.datetime", frozen_poll), \
             patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            result = self.handler.lambda_handler({}, FakeContext())

        # El resultado y los campos ya existentes son idénticos al escenario
        # sin GTFS-RT (test_galicia_train_passed_zamora.py): el fallo de
        # trip_updates_LD.json no afecta en nada al camino probado.
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["recorded"], 1)
        item = self.get_item("G100", "2026-01-05")
        self.assertTrue(item["entregado"])
        self.assertTrue(item["capturado_en_zamora"])
        self.assertEqual(item["hora_paso_zamora"], "09:34")
        self.assertEqual(item["hora_paso_zamora"], item["hora_llegada_corregida"])
        # Los campos GTFS-RT simplemente no están presentes.
        self.assertNotIn("minutos_retraso_gtfsrt", item)
        self.assertNotIn("hora_llegada_gtfsrt", item)
        self.assertNotIn("hora_paso_zamora_gtfsrt", item)

        next_day = MONDAY + timedelta(days=1)
        frozen_dump = make_frozen_datetime(madrid_time_to_utc(next_day, 0, 15))
        with patch("handler.datetime", frozen_dump):
            dump_result = self.handler.daily_dump_handler({}, FakeContext())

        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=dump_result["key"])["Body"].read()
        records = {r["cod_comercial"]: r for r in
                   (json.loads(line) for line in body.decode("utf-8").splitlines())}
        record = records["G100"]
        self.assertEqual(record["minutos_retraso"], 4)
        self.assertFalse(record["cancelado"])
        self.assertIsNone(record["minutos_retraso_gtfsrt"])
        self.assertIsNone(record["hora_llegada_gtfsrt"])
        self.assertIsNone(record["hora_paso_zamora_gtfsrt"])


if __name__ == "__main__":
    unittest.main()
