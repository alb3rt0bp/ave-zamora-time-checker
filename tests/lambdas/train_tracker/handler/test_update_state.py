import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 7, 30, tzinfo=TZ)

SCHEDULED = {
    "cod_comercial": "M100",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_llegada_destino": "08:30",
}


class TestUpdateState(HandlerTestCase):
    def test_persists_expected_fields(self):
        self.handler._update_state("M100", SCHEDULED, 5, NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["cod_comercial"], "M100")
        self.assertEqual(item["sentido"], "Madrid")
        self.assertEqual(item["tipo_dia"], "laborable")
        self.assertEqual(item["hora_programada"], "08:30")
        self.assertEqual(item["ult_retraso"], 5)
        self.assertFalse(item["entregado"])
        self.assertFalse(item["capturado_en_zamora"])
        self.assertNotIn("cod_est_ant", item)
        self.assertNotIn("sk", item)

    def test_computes_hora_llegada_corregida_with_delay(self):
        self.handler._update_state("M100", SCHEDULED, 15, NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["hora_llegada_corregida"], "08:45")

    def test_capturado_en_zamora_flag_is_persisted(self):
        self.handler._update_state("M100", SCHEDULED, 0, NOW, capturado_en_zamora=True)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertTrue(item["capturado_en_zamora"])

    def test_overwrites_previous_item_for_same_train_and_day(self):
        self.handler._update_state("M100", SCHEDULED, 5, NOW)
        self.handler._update_state("M100", SCHEDULED, 20, NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["ult_retraso"], 20)

    def test_hora_paso_zamora_absent_when_not_given(self):
        self.handler._update_state("M100", SCHEDULED, 5, NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertNotIn("hora_paso_zamora", item)

    def test_hora_paso_zamora_persisted_when_given(self):
        self.handler._update_state("M100", SCHEDULED, 5, NOW, hora_paso_zamora="07:03")

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["hora_paso_zamora"], "07:03")

    def test_hora_paso_zamora_dropped_by_put_item_when_omitted_on_a_later_call(self):
        # Regresión: _update_state usa put_item (reemplaza el item entero), así
        # que un valor fijado en un ciclo anterior desaparece si la siguiente
        # llamada no lo reenvía explícitamente. El caller es responsable de
        # releerlo del estado previo (ver _process_madrid_train).
        self.handler._update_state("M100", SCHEDULED, 5, NOW, hora_paso_zamora="07:03")
        self.handler._update_state("M100", SCHEDULED, 8, NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertNotIn("hora_paso_zamora", item)


if __name__ == "__main__":
    unittest.main()
