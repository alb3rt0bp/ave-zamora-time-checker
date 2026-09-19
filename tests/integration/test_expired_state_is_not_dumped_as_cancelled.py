"""
Escenario de integración (regresión del 2026-09-18): el TTL de DynamoDB barre
el estado de un día ANTES de que el volcado diario llegue a leerlo.

Aquel día el TTL antiguo expiraba a las 00:30 y el volcado corría a las 02:15,
así que el barrido se llevó por delante los trenes del día y su marcador
SEED#. Con el sembrado corriendo también en el tramo de madrugada, el
siguiente ciclo de polling volvía a sembrar el día entero como placeholders
sin entregar, y el volcado publicó en el Data Lake una jornada completa de
cancelaciones falsas (todos los trenes salvo el último, el único que seguía
circulando a esa hora y llegó a capturarse en vivo).

Aquí se reproduce esa secuencia exacta. Lo que debe pasar ahora:
  - el tramo de madrugada NO resiembra el día barrido,
  - el volcado detecta que falta el marcador y aborta avisando por SNS,
    en vez de escribir el fichero JSONL con las cancelaciones falsas.
"""
import unittest
from datetime import timedelta
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

TUESDAY = MONDAY + timedelta(days=1)

G100_EN_ZAMORA = {
    "codComercial": "G100",
    "codEstAnt": "30200",  # ZAMORA_CODE
    "codEstSig": "40000",
    "ultRetraso": 4,
}


class FakeContext:
    aws_request_id = "integration-expired-state"


class TestExpiredStateIsNotDumpedAsCancelled(HandlerTestCase):
    def _poll_monday(self):
        """Ciclo normal del lunes: siembra el día y captura G100 en Zamora."""
        frozen = make_frozen_datetime(madrid_time_to_utc(MONDAY, 8, 20))
        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([G100_EN_ZAMORA])
            self.handler.lambda_handler({}, FakeContext())

    def _expire_mondays_state(self):
        """Simula el barrido por TTL: borra TODO el estado del lunes."""
        for item in self.table.scan()["Items"]:
            if item["pk"].endswith("#2026-01-05") or item["pk"] == "SEED#2026-01-05":
                self.table.delete_item(Key={"pk": item["pk"]})

    def _poll_night_tail(self):
        """Ciclo del tramo de madrugada (martes 00:35, día operativo = lunes)."""
        frozen = make_frozen_datetime(madrid_time_to_utc(TUESDAY, 0, 35))
        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([])
            self.handler.lambda_handler({}, FakeContext())

    def _dump_tuesday(self):
        frozen = make_frozen_datetime(madrid_time_to_utc(TUESDAY, 2, 15))
        with patch("handler.datetime", frozen):
            return self.handler.daily_dump_handler({}, FakeContext())

    def test_night_tail_does_not_reseed_the_expired_day(self):
        self._poll_monday()
        self._expire_mondays_state()

        self._poll_night_tail()

        self.assertIsNone(self.get_item("M100", "2026-01-05"))
        self.assertIsNone(self.get_item("G100", "2026-01-05"))

    def test_dump_aborts_instead_of_writing_false_cancellations(self):
        self._poll_monday()
        self._expire_mondays_state()
        self._poll_night_tail()

        result = self._dump_tuesday()

        self.assertEqual(result["statusCode"], 500)
        self.assertEqual(result["reason"], "seed_marker_missing")
        self.assertNotIn("Contents", self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET))
        alerts = self.get_published_data_quality_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertIn("estado del día perdido", alerts[0]["subject"])

    def test_dump_aborts_even_if_the_night_tail_captured_one_train(self):
        # Matiz del caso real: tras el barrido, el único tren que seguía
        # circulando SÍ se captura en vivo en la madrugada y crea su item de
        # cero. El día sigue siendo irrecuperable (le faltan los demás), así
        # que tampoco se vuelca a medias.
        self._poll_monday()
        self._expire_mondays_state()

        frozen = make_frozen_datetime(madrid_time_to_utc(TUESDAY, 0, 35))
        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([G100_EN_ZAMORA])
            self.handler.lambda_handler({}, FakeContext())

        result = self._dump_tuesday()

        self.assertEqual(result["reason"], "seed_marker_missing")
        self.assertNotIn("Contents", self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET))

    def test_ttl_now_outlives_the_daily_dump(self):
        # La causa raíz: el estado del lunes debe seguir vivo cuando corre el
        # volcado del martes a las 02:15, con margen de sobra.
        self._poll_monday()

        ttl = int(self.get_item("G100", "2026-01-05")["ttl"])
        dump_run = int(madrid_time_to_utc(TUESDAY, 2, 15).timestamp())

        self.assertGreater(ttl, dump_run)
        self.assertGreaterEqual((ttl - dump_run) / 3600, 24)

    def test_the_normal_day_still_dumps(self):
        # Control: sin barrido de por medio, el volcado sigue funcionando.
        self._poll_monday()

        result = self._dump_tuesday()

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["written"], 2)  # G100 capturado + M100 cancelado


if __name__ == "__main__":
    unittest.main()
