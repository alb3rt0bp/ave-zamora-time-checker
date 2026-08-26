"""
Escenario de integración para la resolución del horario del día desde GTFS
(ver lambdas/train_tracker/schedule_resolver.py). Cubre, a través de
lambda_handler de punta a punta con AWS mockeado (moto) y la descarga GTFS
mockeada vía urllib:
  1. Camino feliz: primer ciclo del día sin caché en S3 → descarga y parsea
     el GTFS, siembra DynamoDB con los trenes resueltos y cachea el
     resultado en S3 (schedules/{fecha}.json).
  2. La descarga del GTFS falla → cae al fichero estático de reserva
     (train_schedules_sample.json) y publica una alerta de calidad de dato.
  3. Ya existe una caché en S3 para hoy → nunca se llega a descargar el
     GTFS, y se siembra con el contenido cacheado.
"""
import json
import unittest
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import FakeHTTPResponse, fake_urlopen_dispatch, raise_url_error
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc
from tests.dummies.gtfs_samples import GTFS_FILES, to_zip_bytes


class FakeContext:
    aws_request_id = "integration-gtfs-schedule-resolution"


# 05:00 es anterior a la ventana de cualquier tren de estos escenarios (el
# más temprano abre a las 06:41 = 07:41 - 1h), así que ningún test de este
# fichero necesita mockear flotaLD.json: solo se ejercita la resolución del
# horario y el sembrado en DynamoDB.
FROZEN_EARLY_MORNING = make_frozen_datetime(madrid_time_to_utc(MONDAY, 5, 0))


class TestGtfsScheduleResolutionHappyPath(HandlerTestCase):
    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    def test_downloads_gtfs_seeds_dynamodb_and_caches_to_s3(self):
        with patch("handler.datetime", FROZEN_EARLY_MORNING), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = fake_urlopen_dispatch({
                "google_transit.zip": FakeHTTPResponse(to_zip_bytes()),
            })
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)

        # 04154 (TRIP_M1) y 04999 (TRIP_D1/TRIP_D2 deduplicados) son los
        # únicos trenes activos en MONDAY (laborable) del fixture GTFS — ver
        # tests/dummies/gtfs_samples.py.
        m1 = self.get_item("04154", "2026-01-05")
        m999 = self.get_item("04999", "2026-01-05")
        self.assertIsNotNone(m1)
        self.assertIsNotNone(m999)
        self.assertEqual(m1["hora_programada"], "08:49")

        # El fichero estático de reserva (M100/G100) NO se ha usado.
        self.assertIsNone(self.get_item("M100", "2026-01-05"))

        cached = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key="schedules/2026-01-05.json")
        cached_trains = {t["cod_comercial"] for t in json.loads(cached["Body"].read())["trains"]}
        self.assertEqual(cached_trains, {"04154", "04999"})

        self.assertEqual(self.get_published_data_quality_alerts(), [])


class TestGtfsScheduleResolutionDownloadFailure(HandlerTestCase):
    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    def test_falls_back_to_static_schedule_and_alerts(self):
        with patch("handler.datetime", FROZEN_EARLY_MORNING), \
             patch("urllib.request.urlopen", side_effect=raise_url_error):
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)

        # Fallback: M100/G100 (laborable) del fichero estático de reserva.
        self.assertIsNotNone(self.get_item("M100", "2026-01-05"))
        self.assertIsNotNone(self.get_item("G100", "2026-01-05"))
        self.assertIsNone(self.get_item("04154", "2026-01-05"))

        # No se cachea nada en S3 si la resolución desde GTFS falló.
        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)

        alerts = self.get_published_data_quality_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertIn("2026-01-05", alerts[0]["message"])


class TestGtfsScheduleResolutionCacheHit(HandlerTestCase):
    @patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True)
    def test_uses_existing_cache_without_downloading_gtfs(self):
        cached_trains = [{
            "cod_comercial": "CACHED1", "sentido": "Madrid", "tipo_dia": "laborable",
            "hora_salida": "07:00", "hora_llegada_destino": "08:15",
        }]
        self.s3.put_object(
            Bucket=self.handler.S3_BUCKET, Key="schedules/2026-01-05.json",
            Body=json.dumps({"trains": cached_trains}).encode("utf-8"),
        )

        with patch("handler.datetime", FROZEN_EARLY_MORNING), \
             patch("urllib.request.urlopen") as mock_urlopen:
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        mock_urlopen.assert_not_called()

        self.assertIsNotNone(self.get_item("CACHED1", "2026-01-05"))
        self.assertIsNone(self.get_item("M100", "2026-01-05"))
        self.assertIsNone(self.get_item("04154", "2026-01-05"))


if __name__ == "__main__":
    unittest.main()
