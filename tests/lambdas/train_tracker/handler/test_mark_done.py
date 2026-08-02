import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 45, tzinfo=TZ)


class TestMarkDone(HandlerTestCase):
    def setUp(self):
        super().setUp()
        self.table.put_item(
            Item={
                "pk": f"M100#{NOW.date().isoformat()}",
                "entregado": False,
            }
        )

    def test_sets_entregado_true(self):
        self.handler._mark_done("M100", NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertTrue(item["entregado"])

    def test_always_sets_ttl_even_without_prior_update_state(self):
        expected_ttl = self.handler._end_of_day_ttl(NOW)

        self.handler._mark_done("M100", NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["ttl"], expected_ttl)

    def test_sets_hora_llegada_corregida_when_given(self):
        self.handler._mark_done("M100", NOW, hora_llegada_corregida="08:47")

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["hora_llegada_corregida"], "08:47")

    def test_sets_capturado_en_zamora_when_given(self):
        self.handler._mark_done("M100", NOW, capturado_en_zamora=True)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertTrue(item["capturado_en_zamora"])

    def test_does_not_touch_capturado_en_zamora_when_not_given(self):
        self.table.update_item(
            Key={"pk": f"M100#{NOW.date().isoformat()}"},
            UpdateExpression="SET capturado_en_zamora = :v",
            ExpressionAttributeValues={":v": True},
        )

        self.handler._mark_done("M100", NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertTrue(item["capturado_en_zamora"])

    def test_sets_ult_retraso_when_given(self):
        # Regresión: ult_retraso debe poder refrescarse en el mismo momento
        # que hora_llegada_corregida, para que ambos campos queden consistentes
        # entre sí (antes, ult_retraso se quedaba con el valor desfasado de
        # la última llamada a _update_state).
        self.table.update_item(
            Key={"pk": f"M100#{NOW.date().isoformat()}"},
            UpdateExpression="SET ult_retraso = :v",
            ExpressionAttributeValues={":v": 3},
        )

        self.handler._mark_done("M100", NOW, hora_llegada_corregida="08:47", ult_retraso=6)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["ult_retraso"], 6)

    def test_does_not_touch_ult_retraso_when_not_given(self):
        self.table.update_item(
            Key={"pk": f"M100#{NOW.date().isoformat()}"},
            UpdateExpression="SET ult_retraso = :v",
            ExpressionAttributeValues={":v": 3},
        )

        self.handler._mark_done("M100", NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["ult_retraso"], 3)

    def test_sets_hora_paso_zamora_when_given(self):
        self.handler._mark_done("M100", NOW, hora_paso_zamora="07:03")

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["hora_paso_zamora"], "07:03")

    def test_does_not_touch_hora_paso_zamora_when_not_given(self):
        # update_item es un update parcial: a diferencia de _update_state
        # (put_item), no tocar el parámetro deja el atributo existente
        # intacto. Así es como sobrevive hora_paso_zamora hasta la llegada a
        # Chamartín en _process_madrid_train.
        self.table.update_item(
            Key={"pk": f"M100#{NOW.date().isoformat()}"},
            UpdateExpression="SET hora_paso_zamora = :v",
            ExpressionAttributeValues={":v": "07:03"},
        )

        self.handler._mark_done("M100", NOW)

        item = self.get_item("M100", NOW.date().isoformat())
        self.assertEqual(item["hora_paso_zamora"], "07:03")


if __name__ == "__main__":
    unittest.main()
