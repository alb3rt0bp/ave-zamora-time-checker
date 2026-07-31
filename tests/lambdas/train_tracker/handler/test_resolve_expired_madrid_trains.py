import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY

TZ = ZoneInfo("Europe/Madrid")


def _at(hh, mm):
    return datetime(MONDAY.year, MONDAY.month, MONDAY.day, hh, mm, tzinfo=TZ)


class TestResolveExpiredMadridTrains(HandlerTestCase):
    """
    El fixture de horarios (tests/dummies/train_schedules_sample.json) define
    M100 (Madrid, laborable, hora_llegada_destino 08:30) y G100 (Galicia).
    """

    def _put_state(self, cod, now, **overrides):
        item = {
            "pk": f"{cod}#{now.date().isoformat()}",
            "entregado": False,
            "ult_retraso": 0,
            "capturado_en_zamora": True,
        }
        item.update(overrides)
        self.table.put_item(Item=item)

    def test_no_state_at_all_is_skipped(self):
        resolved = self.handler._resolve_expired_madrid_trains(_at(23, 0), SAMPLE_LOG_EXTRA)
        self.assertEqual(resolved, 0)

    def test_already_entregado_is_skipped(self):
        self._put_state("M100", _at(23, 0), entregado=True)

        resolved = self.handler._resolve_expired_madrid_trains(_at(23, 0), SAMPLE_LOG_EXTRA)

        self.assertEqual(resolved, 0)

    def test_still_within_window_is_not_resolved(self):
        # 08:30 + 0 + 10 = 08:40 → a las 08:39 sigue dentro de ventana.
        self._put_state("M100", _at(8, 39))

        resolved = self.handler._resolve_expired_madrid_trains(_at(8, 39), SAMPLE_LOG_EXTRA)

        self.assertEqual(resolved, 0)
        item = self.get_item("M100", _at(8, 39).date().isoformat())
        self.assertFalse(item["entregado"])

    def test_past_window_marks_entregado_with_last_known_data(self):
        # ventana = 08:30 + 7 (retraso) + 10 = 08:47; a las 08:48 ya cerró.
        self._put_state("M100", _at(8, 48), ult_retraso=7)

        resolved = self.handler._resolve_expired_madrid_trains(_at(8, 48), SAMPLE_LOG_EXTRA)

        self.assertEqual(resolved, 1)
        item = self.get_item("M100", _at(8, 48).date().isoformat())
        self.assertTrue(item["entregado"])
        # El polling ya no escribe a S3: eso lo hace daily_dump_handler.
        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)

    def test_past_window_never_seen_is_not_forced_entregado(self):
        # Tren nunca visto en flotaLD.json (p. ej. cancelado por huelga): el
        # placeholder de _seed_todays_trains deja capturado_en_zamora=False,
        # y así se queda si nunca hay datos reales de Renfe.
        self._put_state("M100", _at(8, 48), capturado_en_zamora=False)

        resolved = self.handler._resolve_expired_madrid_trains(_at(8, 48), SAMPLE_LOG_EXTRA)

        self.assertEqual(resolved, 0)
        item = self.get_item("M100", _at(8, 48).date().isoformat())
        self.assertFalse(item["entregado"])

    def test_galicia_trains_are_never_touched(self):
        self._put_state("G100", _at(23, 0))  # sentido Galicia en el fixture

        resolved = self.handler._resolve_expired_madrid_trains(_at(23, 0), SAMPLE_LOG_EXTRA)

        self.assertEqual(resolved, 0)
        item = self.get_item("G100", _at(23, 0).date().isoformat())
        self.assertFalse(item["entregado"])


if __name__ == "__main__":
    unittest.main()
