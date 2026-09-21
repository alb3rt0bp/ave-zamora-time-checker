import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json, raise_url_error
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.reference_dates import MONDAY
from tests.dummies.renfe_samples import TRAIN_G100_EN_ZAMORA

TZ = ZoneInfo("Europe/Madrid")
TUESDAY = MONDAY + timedelta(days=1)


class FakeContext:
    aws_request_id = "test-request-id"


def _frozen_now(hh, mm):
    """Instante UTC equivalente a hh:mm hora de Madrid del lunes de referencia."""
    local = datetime(MONDAY.year, MONDAY.month, MONDAY.day, hh, mm, tzinfo=TZ)
    return local.astimezone(timezone.utc)


def _frozen_now_next_day(hh, mm):
    """
    Igual que _frozen_now pero en el día calendario siguiente (martes) —
    para simular el tramo de polling de madrugada [00:00, NIGHT_TAIL_WINDOW_MINUTES)
    que, pese a caer ya en el día calendario siguiente, sigue perteneciendo
    operativamente al lunes (ver _operational_date en handler.py).
    """
    local = datetime(TUESDAY.year, TUESDAY.month, TUESDAY.day, hh, mm, tzinfo=TZ)
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
            "entregado": False,
            "ult_retraso": 0,
            "capturado_en_zamora": True,
        })
        self.table.put_item(Item={
            "pk": "G100#2026-01-05",
            "entregado": True,
        })
        frozen = make_frozen_datetime(_frozen_now(8, 41))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["recorded"], 1)

    def test_seeds_todays_trains_on_first_cycle(self):
        # A las 05:00 no hay trenes activos, pero el sembrado (paso 0) debe
        # haber creado los placeholders de M100 y G100 (laborable) igualmente.
        frozen = make_frozen_datetime(_frozen_now(5, 0))

        with patch("handler.datetime", frozen), patch("urllib.request.urlopen"):
            self.handler.lambda_handler({}, FakeContext())

        m100 = self.get_item("M100", "2026-01-05")
        g100 = self.get_item("G100", "2026-01-05")
        self.assertIsNotNone(m100)
        self.assertIsNotNone(g100)
        self.assertFalse(m100["entregado"])
        self.assertFalse(g100["entregado"])

    def test_night_tail_window_resolves_previous_day_straggler(self):
        # M100 (Madrid) quedó capturado_en_zamora pero sin resolver desde el
        # lunes (su ventana normal, 08:30+0+10=08:40, ya cerró hace horas sin
        # que ningún ciclo lo detectara). A las 00:30 del martes (tramo de
        # madrugada) sigue sin aparecer en la flota → debe resolverse usando
        # el día OPERATIVO correcto (lunes), no el día calendario de "ahora"
        # (martes): esta es exactamente la regresión que motivó
        # _operational_date/_schedule_datetime — antes de este cambio,
        # ancorar la hora programada en el día calendario de "ahora" hacía
        # que el tren pareciera "aún no ha llegado" indefinidamente.
        self.table.put_item(Item={
            "pk": "M100#2026-01-05",
            "entregado": False,
            "ult_retraso": 0,
            "capturado_en_zamora": True,
        })
        frozen = make_frozen_datetime(_frozen_now_next_day(0, 15))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([])  # M100 ya no está en la flota
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["recorded"], 1)
        item = self.get_item("M100", "2026-01-05")
        self.assertTrue(item["entregado"])

    def test_night_tail_window_keeps_checking_train_still_in_fleet(self):
        # G100 (Galicia) aún no ha pasado por Zamora a las 00:15 del martes
        # (tramo de madrugada): sigue comprobándose contra flotaLD.json en
        # vez de darse por perdido solo porque el polling normal ya paró.
        self.table.put_item(Item={
            "pk": "G100#2026-01-05",
            "entregado": False,
            "ult_retraso": 90,
            "capturado_en_zamora": False,
        })
        frozen = make_frozen_datetime(_frozen_now_next_day(0, 15))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([TRAIN_G100_EN_ZAMORA])
            result = self.handler.lambda_handler({}, FakeContext())

        self.assertEqual(result["recorded"], 1)
        item = self.get_item("G100", "2026-01-05")
        self.assertTrue(item["entregado"])

    def test_night_tail_window_does_not_reseed_or_use_tomorrows_schedule(self):
        # El día OPERATIVO a las 00:15 del martes sigue siendo el lunes: no
        # debe aparecer ningún placeholder para el martes (2026-01-06), y el
        # marcador SEED#2026-01-05 (ya sembrado durante el lunes) evita
        # resembrar M100/G100.
        self.table.put_item(Item={"pk": "SEED#2026-01-05", "ttl": 0})
        self.table.put_item(Item={
            "pk": "M100#2026-01-05", "entregado": False, "ult_retraso": 0, "capturado_en_zamora": False,
        })
        frozen = make_frozen_datetime(_frozen_now_next_day(0, 15))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([])
            self.handler.lambda_handler({}, FakeContext())

        self.assertIsNone(self.get_item("M100", "2026-01-06"))
        self.assertIsNone(self.get_item("G100", "2026-01-06"))

    def test_night_tail_window_does_not_reseed_a_day_whose_marker_expired(self):
        # LA regresión del 2026-09-18: el TTL antiguo (00:30) barrió el estado
        # del lunes — marcador SEED# incluido — a mitad del tramo de
        # madrugada. Con el sembrado corriendo también en ese tramo, el
        # siguiente ciclo resembraba los 54 trenes del día como placeholders
        # sin entregar, y el volcado de las 02:15 los daba todos por
        # cancelados. En el tramo de madrugada NO se siembra: sin marcador ni
        # items, la tabla se queda vacía y el volcado abortará avisando, en
        # vez de publicar un día entero de cancelaciones falsas.
        frozen = make_frozen_datetime(_frozen_now_next_day(0, 20))

        with patch("handler.datetime", frozen), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json([])
            self.handler.lambda_handler({}, FakeContext())

        self.assertIsNone(self.get_item("M100", "2026-01-05"))
        self.assertIsNone(self.get_item("G100", "2026-01-05"))
        self.assertIsNone(self.table.get_item(Key={"pk": "SEED#2026-01-05"}).get("Item"))

    def test_cycle_at_00_30_is_no_longer_in_the_night_tail_window(self):
        # NIGHT_TAIL_WINDOW_MINUTES por defecto = 30 → a las 00:30 el día
        # operativo ya vuelve a ser el día calendario (martes): se siembra
        # el martes con normalidad, como cualquier primer ciclo del día.
        frozen = make_frozen_datetime(_frozen_now_next_day(0, 30))

        with patch("handler.datetime", frozen), patch("urllib.request.urlopen"):
            self.handler.lambda_handler({}, FakeContext())

        self.assertIsNotNone(self.get_item("M100", "2026-01-06"))
        self.assertIsNone(self.get_item("M100", "2026-01-05"))


if __name__ == "__main__":
    unittest.main()
