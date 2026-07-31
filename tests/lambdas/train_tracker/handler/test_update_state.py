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


if __name__ == "__main__":
    unittest.main()
