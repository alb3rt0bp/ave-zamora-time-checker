import unittest
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY
from tests.dummies.renfe_samples import TRAIN_M100_EN_CHAMARTIN, TRAIN_M100_EN_RUTA, TRAIN_M100_EN_ZAMORA

from datalake_writer import DatalakeWriter

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
    def setUp(self):
        super().setUp()
        self.writer = DatalakeWriter(self.s3, self.handler.S3_BUCKET, SAMPLE_LOG_EXTRA)

    def _put_state(self, now, **overrides):
        item = {
            "pk": f"M100#{now.date().isoformat()}",
            "sk": "TRACKING",
            "done": False,
            "ult_retraso": 0,
            "cod_est_ant": "10000",
            "capturado_en_zamora": False,
        }
        item.update(overrides)
        self.table.put_item(Item=item)

    def test_done_short_circuits(self):
        self._put_state(_at(8, 40), done=True)
        mock_writer = MagicMock()

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 40), SAMPLE_LOG_EXTRA, mock_writer)

        self.assertFalse(result)
        mock_writer.write.assert_not_called()

    def test_via1_not_seen_before_returns_false(self):
        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(7, 30), SAMPLE_LOG_EXTRA, self.writer)
        self.assertFalse(result)

    def test_via1_seen_before_but_not_captured_in_zamora_returns_false(self):
        self._put_state(_at(8, 40), capturado_en_zamora=False)

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 40), SAMPLE_LOG_EXTRA, self.writer)

        self.assertFalse(result)
        item = self.get_item("M100", _at(8, 40).date().isoformat())
        self.assertFalse(item["done"])

    def test_via1_before_retry_gate_returns_false(self):
        # hora_llegada_destino (08:30) + ult_retraso conocido (0) = 08:30
        self._put_state(_at(8, 20), capturado_en_zamora=True, ult_retraso=0)

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 20), SAMPLE_LOG_EXTRA, self.writer)

        self.assertFalse(result)

    def test_via1_after_retry_gate_records_and_marks_done(self):
        # gate = 08:30 + 10 = 08:40; a las 08:41 ya se acepta la desaparición.
        self._put_state(_at(8, 41), capturado_en_zamora=True, ult_retraso=10, cod_est_ant="90000")

        result = self.handler._process_madrid_train(MADRID_SCHEDULED, None, _at(8, 41), SAMPLE_LOG_EXTRA, self.writer)

        self.assertTrue(result)
        item = self.get_item("M100", _at(8, 41).date().isoformat())
        self.assertTrue(item["done"])
        listed = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)["Contents"]
        self.assertEqual(len(listed), 1)

    def test_via2_chamartin_records_and_marks_done_regardless_of_zamora_flag(self):
        result = self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_CHAMARTIN, _at(8, 35), SAMPLE_LOG_EXTRA, self.writer
        )

        self.assertTrue(result)
        item = self.get_item("M100", _at(8, 35).date().isoformat())
        self.assertTrue(item["done"])
        # No había pasado antes por Zamora (no hay estado previo) → se refleja False.
        self.assertFalse(item.get("capturado_en_zamora", False))

    def test_via2_chamartin_refreshes_ult_retraso_and_hora_llegada_real(self):
        # Regresión: un ciclo anterior deja ult_retraso=3 en Dynamo; en el
        # ciclo en que se detecta la llegada a Chamartín el retraso real de
        # Renfe es el de TRAIN_M100_EN_CHAMARTIN (5). El item final debe
        # reflejar ese retraso fresco, no el desfasado.
        self._put_state(_at(8, 35), capturado_en_zamora=True, ult_retraso=3, cod_est_ant="90000")

        self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_CHAMARTIN, _at(8, 35), SAMPLE_LOG_EXTRA, self.writer
        )

        item = self.get_item("M100", _at(8, 35).date().isoformat())
        self.assertEqual(item["ult_retraso"], TRAIN_M100_EN_CHAMARTIN["ultRetraso"])

        from datetime import datetime, timedelta
        h, m = map(int, MADRID_SCHEDULED["hora_llegada_destino"].split(":"))
        expected_hora_real = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=int(item["ult_retraso"]))
        ).strftime("%H:%M")
        self.assertEqual(item["hora_llegada_real"], expected_hora_real)

    def test_en_route_updates_state_without_recording(self):
        result = self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_RUTA, _at(7, 30), SAMPLE_LOG_EXTRA, self.writer
        )

        self.assertFalse(result)
        item = self.get_item("M100", _at(7, 30).date().isoformat())
        self.assertFalse(item["done"])
        self.assertEqual(item["cod_est_ant"], TRAIN_M100_EN_RUTA["codEstAnt"])

    def test_en_route_sets_capturado_en_zamora_when_passing_through_zamora(self):
        result = self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_ZAMORA, _at(7, 55), SAMPLE_LOG_EXTRA, self.writer
        )

        self.assertFalse(result)
        item = self.get_item("M100", _at(7, 55).date().isoformat())
        self.assertTrue(item["capturado_en_zamora"])

    def test_en_route_keeps_capturado_en_zamora_true_once_set(self):
        self._put_state(_at(8, 0), capturado_en_zamora=True, cod_est_ant="30200")

        self.handler._process_madrid_train(
            MADRID_SCHEDULED, TRAIN_M100_EN_RUTA, _at(8, 5), SAMPLE_LOG_EXTRA, self.writer
        )

        item = self.get_item("M100", _at(8, 5).date().isoformat())
        self.assertTrue(item["capturado_en_zamora"])


if __name__ == "__main__":
    unittest.main()
