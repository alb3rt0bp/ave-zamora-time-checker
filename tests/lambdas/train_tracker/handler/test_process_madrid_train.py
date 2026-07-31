import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY
from tests.dummies.renfe_samples import (
    TRAIN_M100_EN_CHAMARTIN,
    TRAIN_M100_EN_CHAMARTIN_CON_RETRASO,
    TRAIN_M100_EN_RUTA,
    TRAIN_M100_EN_ZAMORA,
)

TZ = ZoneInfo("Europe/Madrid")

MADRID_SCHEDULED = {
    "cod_comercial": "M100",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_llegada_destino": "08:30",
}


def _at(hh, mm):
    return datetime(MONDAY.year, MONDAY.month, MONDAY.day, hh, mm, tzinfo=TZ)


class TestProcessMadridTrain(HandlerTestCase):
    def _put_state(self, now, **overrides):
        item = {
            "pk": f"M100#{now.date().isoformat()}",
            "entregado": False,
            "ult_retraso": 0,
            "capturado_en_zamora": False,
        }
        item.update(overrides)
        self.table.put_item(Item=item)

    def test_entregado_short_circuits(self):
        self._put_state(_at(8, 40), entregado=True)

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 40), SAMPLE_LOG_EXTRA)

        self.assertFalse(result)

    def test_via1_not_seen_before_returns_false(self):
        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(7, 30), SAMPLE_LOG_EXTRA)
        self.assertFalse(result)

    def test_via1_seen_before_but_not_captured_in_zamora_returns_false(self):
        self._put_state(_at(8, 40), capturado_en_zamora=False)

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 40), SAMPLE_LOG_EXTRA)

        self.assertFalse(result)
        item = self.get_item("M100", _at(8, 40).date().isoformat())
        self.assertFalse(item["entregado"])

    def test_via1_before_retry_gate_returns_false(self):
        # hora_llegada_destino (08:30) + ult_retraso conocido (0) = 08:30
        self._put_state(_at(8, 20), capturado_en_zamora=True, ult_retraso=0)

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 20), SAMPLE_LOG_EXTRA)

        self.assertFalse(result)

    def test_via1_after_retry_gate_marks_entregado(self):
        # gate = 08:30 + 10 = 08:40; a las 08:41 ya se acepta la desaparición.
        self._put_state(_at(8, 41), capturado_en_zamora=True, ult_retraso=10)

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 41), SAMPLE_LOG_EXTRA)

        self.assertTrue(result)
        item = self.get_item("M100", _at(8, 41).date().isoformat())
        self.assertTrue(item["entregado"])
        # El polling ya no escribe a S3: eso lo hace daily_dump_handler.
        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)
        # ult_retraso=10 no supera el umbral (15) → sin alerta.
        self.assertEqual(self.get_published_delay_alerts(), [])

    def test_via1_after_retry_gate_with_high_delay_publishes_alert(self):
        # gate = 08:30 + 20 = 08:50; a las 08:51 ya se acepta la desaparición.
        self._put_state(
            _at(8, 51), capturado_en_zamora=True, ult_retraso=20, hora_llegada_corregida="08:50"
        )

        self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 51), SAMPLE_LOG_EXTRA)

        [alert] = self.get_published_delay_alerts()
        self.assertEqual(alert["cod_comercial"], "M100")
        self.assertEqual(alert["minutos_retraso"], 20)
        self.assertEqual(alert["hora_llegada_corregida"], "08:50")

    def test_via2_chamartin_marks_entregado_regardless_of_zamora_flag(self):
        result = self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_CHAMARTIN, _at(8, 35), SAMPLE_LOG_EXTRA
        )

        self.assertTrue(result)
        item = self.get_item("M100", _at(8, 35).date().isoformat())
        self.assertTrue(item["entregado"])
        # No había pasado antes por Zamora (no hay estado previo) → se refleja False.
        self.assertFalse(item.get("capturado_en_zamora", False))
        # TRAIN_M100_EN_CHAMARTIN trae ultRetraso=5, por debajo del umbral (15).
        self.assertEqual(self.get_published_delay_alerts(), [])

    def test_via2_chamartin_with_high_delay_publishes_alert(self):
        self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_CHAMARTIN_CON_RETRASO, _at(8, 35), SAMPLE_LOG_EXTRA
        )

        [alert] = self.get_published_delay_alerts()
        self.assertEqual(alert["cod_comercial"], "M100")
        self.assertEqual(alert["minutos_retraso"], TRAIN_M100_EN_CHAMARTIN_CON_RETRASO["ultRetraso"])

    def test_via2_chamartin_refreshes_ult_retraso_and_hora_llegada_corregida(self):
        # Regresión: un ciclo anterior deja ult_retraso=3 en Dynamo; en el
        # ciclo en que se detecta la llegada a Chamartín el retraso real de
        # Renfe es el de TRAIN_M100_EN_CHAMARTIN (5). El item final debe
        # reflejar ese retraso fresco, no el desfasado.
        self._put_state(_at(8, 35), capturado_en_zamora=True, ult_retraso=3)

        self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_CHAMARTIN, _at(8, 35), SAMPLE_LOG_EXTRA
        )

        item = self.get_item("M100", _at(8, 35).date().isoformat())
        self.assertEqual(item["ult_retraso"], TRAIN_M100_EN_CHAMARTIN["ultRetraso"])

        h, m = map(int, MADRID_SCHEDULED["hora_llegada_destino"].split(":"))
        expected_hora_corregida = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=int(item["ult_retraso"]))
        ).strftime("%H:%M")
        self.assertEqual(item["hora_llegada_corregida"], expected_hora_corregida)

    def test_en_route_updates_state_without_recording(self):
        result = self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_RUTA, _at(7, 30), SAMPLE_LOG_EXTRA
        )

        self.assertFalse(result)
        item = self.get_item("M100", _at(7, 30).date().isoformat())
        self.assertFalse(item["entregado"])
        self.assertEqual(item["ult_retraso"], TRAIN_M100_EN_RUTA["ultRetraso"])
        self.assertNotIn("cod_est_ant", item)

    def test_en_route_sets_capturado_en_zamora_when_passing_through_zamora(self):
        result = self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_ZAMORA, _at(7, 55), SAMPLE_LOG_EXTRA
        )

        self.assertFalse(result)
        item = self.get_item("M100", _at(7, 55).date().isoformat())
        self.assertTrue(item["capturado_en_zamora"])

    def test_en_route_keeps_capturado_en_zamora_true_once_set(self):
        self._put_state(_at(8, 0), capturado_en_zamora=True)

        self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_RUTA, _at(8, 5), SAMPLE_LOG_EXTRA
        )

        item = self.get_item("M100", _at(8, 5).date().isoformat())
        self.assertTrue(item["capturado_en_zamora"])


if __name__ == "__main__":
    unittest.main()
