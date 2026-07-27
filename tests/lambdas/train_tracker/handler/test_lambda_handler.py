import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json, raise_url_error
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.renfe_samples import TRAIN_G100_EN_ZAMORA

TZ = ZoneInfo("Europe/Madrid")


class FakeContext:
    aws_request_id = "test-request-id"


def _frozen_now(hh, mm):
    """Instante UTC equivalente a hh:mm hora de Madrid del lunes de referencia."""
    local = datetime(MONDAY.year, MONDAY.month, MONDAY.day, hh, mm, tzinfo=TZ)
    return local.astimezone(timezone.utc)


class TestLambdaHandler(HandlerTestCase):
    def test_no_active_trains_skips_flota_fetch(self):
        # Antes de la ventana de cualquier tren del fixture (la más temprana
        # empieza a las 06:00 = hora_salida 07:00 - 1h).
        frozen = make_frozen_datetime(_frozen_now(5, 0))

        with patch("handler.datetime", frozen), patch("urllib.request.urlopen") as mock_urlopen:
            result = self.handler.lambda_handler({}, FakeContext())

        mock_urlopen.assert_not_called()
        self.assertEqual(result, {"statusCode": 200, "active": 0, "recorded": 0})

    def test_returns_503_when_flota_fetch_fails(self):
        frozen = make_frozen_datetime(_frozen_now(8, 10))  # G100 activo

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen", side_effect=raise_url_error):
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 503)

    def test_records_galicia_arrival_and_returns_counts(self):
        frozen = make_frozen_datetime(_frozen_now(8, 10))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([TRAIN_G100_EN_ZAMORA])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["statusCode"], 200)
        self.assertGreaterEqual(result["active"], 1)
        self.assertEqual(result["recorded"], 1)

    def test_resolved_expired_madrid_trains_are_added_to_recorded_count(self):
        # M100 (Madrid) ya fuera de su ventana (08:30 + 0 + 10 = 08:40) pero
        # pendiente en Dynamo → lo recoge _resolve_expired_madrid_trains.
        # G100 (Galicia) ya capturado hoy → no aporta nada al procesar activos.
        self.table.put_item(Item={
            "pk": "M100#2026-01-05",
            "sk": "TRACKING",
            "done": False,
            "ult_retraso": 0,
            "cod_est_ant": "10000",
            "capturado_en_zamora": True,
        })
        self.table.put_item(Item={
            "pk": "G100#2026-01-05",
            "sk": "TRACKING",
            "done": True,
        })
        frozen = make_frozen_datetime(_frozen_now(8, 41))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["recorded"], 1)


if __name__ == "__main__":
    unittest.main()
