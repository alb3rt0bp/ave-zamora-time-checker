"""
Escenario de integración: tren cuya llegada programada cae ya en el día
siguiente — en GTFS, una hora >= 24:00 (el fixture TRIP_MNIGHT / 04777 sale
de Zamora a las 23:05 y llega a Chamartín a las "24:10").

Es la regresión que dejó anotada el arreglo del volcado del 2026-09-18: al
normalizar "24:10" a la hora de reloj "00:10" se perdía el día al que
pertenece, así que ScheduleMatcher cerraba la ventana de ese tren a las
00:20 del MISMO día en que salía — es decir, cerrada desde primera hora de
la mañana. El tren no se monitorizaba nunca y el volcado diario lo
registraba como 'cancelado' un día tras otro.

Aquí se recorre el ciclo completo con el offset ya propagado: polling de
noche (ventana abierta), captura en el tramo de madrugada y volcado con su
retraso real.
"""
import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import FakeHTTPResponse, fake_urlopen_dispatch, fake_urlopen_json
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.gtfs_samples import GTFS_FILES, to_zip_bytes
from tests.dummies.reference_dates import MONDAY
from tests.dummies.time_utils import madrid_time_to_utc

TUESDAY = MONDAY + timedelta(days=1)

# 04777 recién salido de Zamora, con 5 min de retraso.
NIGHT_TRAIN_AT_ZAMORA = {
    "codComercial": "04777",
    "codEstAnt": "30200",
    "codEstSig": "17000",
    "ultRetraso": 5,
}
# El mismo tren ya en Chamartín (última estación), pasada la medianoche.
NIGHT_TRAIN_AT_CHAMARTIN = {
    "codComercial": "04777",
    "codEstAnt": "17000",
    "codEstSig": "",
    "ultRetraso": 5,
}


class FakeContext:
    aws_request_id = "integration-past-midnight"


class TestTrainArrivingPastMidnight(HandlerTestCase):
    def _poll(self, frozen_utc, flota):
        with patch("schedule_resolver.GTFS_SCHEDULE_ENABLED", True), \
             patch("handler.datetime", make_frozen_datetime(frozen_utc)), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = fake_urlopen_dispatch({
                "google_transit.zip": FakeHTTPResponse(to_zip_bytes(GTFS_FILES)),
                "flotaLD.json": fake_urlopen_json(flota),
            })
            return self.handler.lambda_handler({}, FakeContext())

    def test_window_is_open_the_night_before_its_arrival(self):
        # Ventana de 04777: 22:05 (23:05 - 1h) → 00:20 del día siguiente.
        result = self._poll(madrid_time_to_utc(MONDAY, 23, 30), [NIGHT_TRAIN_AT_ZAMORA])

        self.assertGreaterEqual(result["active"], 1)
        item = self.get_item("04777", "2026-01-05")
        self.assertTrue(item["capturado_en_zamora"])
        self.assertEqual(int(item["ult_retraso"]), 5)
        # hora_llegada_destino 00:10 + 5 min de retraso.
        self.assertEqual(item["hora_llegada_corregida"], "00:15")
        self.assertFalse(item["entregado"])

    def test_seeded_with_the_clock_time_of_its_arrival(self):
        self._poll(madrid_time_to_utc(MONDAY, 23, 30), [])

        # El día operativo sigue siendo el lunes aunque el tren llegue el
        # martes: el estado se indexa por el día en que SALE.
        item = self.get_item("04777", "2026-01-05")
        self.assertEqual(item["hora_programada"], "00:10")
        self.assertIsNone(self.get_item("04777", "2026-01-06"))

    def test_no_alert_is_published_for_this_train(self):
        # Sin polling_window coverage check: aunque un tren cruce medianoche,
        # el sistema ya no avisa por ello (no es un problema en sí — el
        # último tren real del día llega sobre las 23:30, mucho antes del
        # cierre del tramo de madrugada a las 00:30).
        self._poll(madrid_time_to_utc(MONDAY, 23, 30), [NIGHT_TRAIN_AT_ZAMORA])

        self.assertEqual(self.get_published_data_quality_alerts(), [])

    def test_captured_in_the_night_tail_and_dumped_with_its_real_delay(self):
        self._poll(madrid_time_to_utc(MONDAY, 23, 30), [NIGHT_TRAIN_AT_ZAMORA])

        # 00:15 del martes: tramo de madrugada, día operativo = lunes.
        self._poll(madrid_time_to_utc(TUESDAY, 0, 15), [NIGHT_TRAIN_AT_CHAMARTIN])

        item = self.get_item("04777", "2026-01-05")
        self.assertTrue(item["entregado"])
        self.assertEqual(item["hora_llegada_corregida"], "00:15")

        with patch("handler.datetime", make_frozen_datetime(madrid_time_to_utc(TUESDAY, 1, 0))):
            dump = self.handler.daily_dump_handler({}, FakeContext())

        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=dump["key"])["Body"].read()
        records = {r["cod_comercial"]: r for r in
                   (json.loads(line) for line in body.decode("utf-8").splitlines())}

        record = records["04777"]
        self.assertFalse(record["cancelado"])
        self.assertEqual(record["minutos_retraso"], 5)
        self.assertEqual(record["hora_programada"], "00:10")
        self.assertEqual(record["hora_llegada_corregida"], "00:15")


if __name__ == "__main__":
    unittest.main()
