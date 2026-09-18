import unittest
from datetime import date

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

TODAY = date(2026, 1, 5)

TRAINS_TODAY = [
    {"cod_comercial": "M100", "sentido": "Madrid", "hora_salida": "07:00", "hora_llegada_destino": "08:30"},
    {"cod_comercial": "G100", "sentido": "Galicia", "hora_salida": "08:00", "hora_llegada_destino": "09:30"},
]


class TestGetPendingTrains(HandlerTestCase):
    def test_train_with_no_state_is_pending(self):
        pending = self.handler._get_pending_trains(TODAY, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        self.assertEqual({t["cod_comercial"] for t in pending}, {"M100", "G100"})

    def test_train_not_yet_entregado_is_pending(self):
        self.table.put_item(Item={"pk": "M100#2026-01-05", "entregado": False})

        pending = self.handler._get_pending_trains(TODAY, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        self.assertIn("M100", {t["cod_comercial"] for t in pending})

    def test_train_already_entregado_is_excluded(self):
        self.table.put_item(Item={"pk": "M100#2026-01-05", "entregado": True})

        pending = self.handler._get_pending_trains(TODAY, TRAINS_TODAY, SAMPLE_LOG_EXTRA)

        self.assertEqual([t["cod_comercial"] for t in pending], ["G100"])


if __name__ == "__main__":
    unittest.main()
