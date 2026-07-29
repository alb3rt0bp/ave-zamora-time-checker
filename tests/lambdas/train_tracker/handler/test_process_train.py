import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY
from tests.dummies.renfe_samples import TRAIN_G100_EN_RUTA, TRAIN_G100_EN_ZAMORA

from datalake_writer import DatalakeWriter

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 10, tzinfo=TZ)

GALICIA_SCHEDULED = {
    "cod_comercial": "G100",
    "sentido": "Galicia",
    "tipo_dia": "laborable",
    "hora_llegada_destino": "09:30",
}

MADRID_SCHEDULED = {
    "cod_comercial": "M100",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_llegada_destino": "08:30",
}


class TestProcessTrain(HandlerTestCase):
    def setUp(self):
        super().setUp()
        self.writer = DatalakeWriter(self.s3, self.handler.S3_BUCKET, SAMPLE_LOG_EXTRA)

    def test_dispatches_madrid_trains_to_process_madrid_train(self):
        # live=None y sin estado previo → rama exclusiva de _process_madrid_train.
        result = self.handler._process_train(MADRID_SCHEDULED, None, NOW, SAMPLE_LOG_EXTRA, self.writer)
        self.assertFalse(result)

    def test_galicia_done_short_circuits_without_touching_writer(self):
        self.table.put_item(
            Item={"pk": f"G100#{NOW.date().isoformat()}", "sk": "TRACKING", "done": True}
        )
        mock_writer = MagicMock()

        result = self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA, NOW, SAMPLE_LOG_EXTRA, mock_writer)

        self.assertFalse(result)
        mock_writer.write.assert_not_called()

    def test_galicia_live_none_returns_false(self):
        mock_writer = MagicMock()

        result = self.handler._process_train(GALICIA_SCHEDULED, None, NOW, SAMPLE_LOG_EXTRA, mock_writer)

        self.assertFalse(result)
        mock_writer.write.assert_not_called()

    def test_galicia_not_yet_at_zamora_updates_state(self):
        result = self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_RUTA, NOW, SAMPLE_LOG_EXTRA, self.writer)

        self.assertFalse(result)
        item = self.get_item("G100", NOW.date().isoformat())
        self.assertEqual(item["cod_est_ant"], TRAIN_G100_EN_RUTA["codEstAnt"])
        self.assertFalse(item["done"])

    def test_galicia_arrival_at_zamora_records_and_marks_done(self):
        result = self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA, NOW, SAMPLE_LOG_EXTRA, self.writer)

        self.assertTrue(result)
        item = self.get_item("G100", NOW.date().isoformat())
        self.assertTrue(item["done"])
        self.assertTrue(item["capturado_en_zamora"])
        listed = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)["Contents"]
        self.assertEqual(len(listed), 1)

    def test_galicia_ult_retraso_stays_consistent_with_hora_llegada_real_across_cycles(self):
        # Regresión: un ciclo anterior deja ult_retraso=2 en Dynamo (vía
        # _update_state); en el ciclo en que se captura el paso por Zamora el
        # retraso real de Renfe ha subido a 4. El item final debe reflejar el
        # retraso de ESTE ciclo (4), no el desfasado del ciclo anterior (2).
        self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_RUTA, NOW, SAMPLE_LOG_EXTRA, self.writer)
        self.assertEqual(self.get_item("G100", NOW.date().isoformat())["ult_retraso"], TRAIN_G100_EN_RUTA["ultRetraso"])

        self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA, NOW, SAMPLE_LOG_EXTRA, self.writer)

        item = self.get_item("G100", NOW.date().isoformat())
        self.assertEqual(item["ult_retraso"], TRAIN_G100_EN_ZAMORA["ultRetraso"])

        h, m = map(int, GALICIA_SCHEDULED["hora_llegada_destino"].split(":"))
        expected_hora_real = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=int(item["ult_retraso"]))
        ).strftime("%H:%M")
        self.assertEqual(item["hora_llegada_real"], expected_hora_real)


if __name__ == "__main__":
    unittest.main()
