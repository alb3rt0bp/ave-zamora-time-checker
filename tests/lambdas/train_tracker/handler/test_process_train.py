import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY
from tests.dummies.renfe_samples import (
    TRAIN_G100_EN_RUTA,
    TRAIN_G100_EN_ZAMORA,
    TRAIN_G100_EN_ZAMORA_CON_RETRASO,
)

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
    def test_dispatches_madrid_trains_to_process_madrid_train(self):
        # live=None y sin estado previo → rama exclusiva de _process_madrid_train.
        result = self.handler._process_train(MADRID_SCHEDULED, None, NOW, SAMPLE_LOG_EXTRA)
        self.assertFalse(result)

    def test_galicia_entregado_short_circuits(self):
        self.table.put_item(
            Item={"pk": f"G100#{NOW.date().isoformat()}", "entregado": True}
        )

        result = self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA, NOW, SAMPLE_LOG_EXTRA)

        self.assertFalse(result)

    def test_galicia_live_none_returns_false(self):
        result = self.handler._process_train(GALICIA_SCHEDULED, None, NOW, SAMPLE_LOG_EXTRA)
        self.assertFalse(result)

    def test_galicia_not_yet_at_zamora_updates_state(self):
        result = self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_RUTA, NOW, SAMPLE_LOG_EXTRA)

        self.assertFalse(result)
        item = self.get_item("G100", NOW.date().isoformat())
        self.assertEqual(item["ult_retraso"], TRAIN_G100_EN_RUTA["ultRetraso"])
        self.assertFalse(item["entregado"])
        self.assertNotIn("cod_est_ant", item)

    def test_galicia_arrival_at_zamora_marks_entregado(self):
        result = self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA, NOW, SAMPLE_LOG_EXTRA)

        self.assertTrue(result)
        item = self.get_item("G100", NOW.date().isoformat())
        self.assertTrue(item["entregado"])
        self.assertTrue(item["capturado_en_zamora"])
        # El polling ya no escribe a S3: eso lo hace daily_dump_handler.
        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)

    def test_galicia_arrival_with_low_delay_does_not_publish_alert(self):
        # TRAIN_G100_EN_ZAMORA trae ultRetraso=4, por debajo del umbral (15).
        self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA, NOW, SAMPLE_LOG_EXTRA)

        self.assertEqual(self.get_published_delay_alerts(), [])

    def test_galicia_arrival_with_high_delay_publishes_alert(self):
        self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA_CON_RETRASO, NOW, SAMPLE_LOG_EXTRA)

        [alert] = self.get_published_delay_alerts()
        self.assertEqual(alert["cod_comercial"], "G100")
        self.assertEqual(alert["minutos_retraso"], TRAIN_G100_EN_ZAMORA_CON_RETRASO["ultRetraso"])

    def test_galicia_ult_retraso_stays_consistent_with_hora_llegada_corregida_across_cycles(self):
        # Regresión: un ciclo anterior deja ult_retraso=2 en Dynamo (vía
        # _update_state); en el ciclo en que se captura el paso por Zamora el
        # retraso real de Renfe ha subido a 4. El item final debe reflejar el
        # retraso de ESTE ciclo (4), no el desfasado del ciclo anterior (2).
        self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_RUTA, NOW, SAMPLE_LOG_EXTRA)
        self.assertEqual(self.get_item("G100", NOW.date().isoformat())["ult_retraso"], TRAIN_G100_EN_RUTA["ultRetraso"])

        self.handler._process_train(GALICIA_SCHEDULED, TRAIN_G100_EN_ZAMORA, NOW, SAMPLE_LOG_EXTRA)

        item = self.get_item("G100", NOW.date().isoformat())
        self.assertEqual(item["ult_retraso"], TRAIN_G100_EN_ZAMORA["ultRetraso"])

        h, m = map(int, GALICIA_SCHEDULED["hora_llegada_destino"].split(":"))
        expected_hora_corregida = (
            datetime(2000, 1, 1, h, m) + timedelta(minutes=int(item["ult_retraso"]))
        ).strftime("%H:%M")
        self.assertEqual(item["hora_llegada_corregida"], expected_hora_corregida)


if __name__ == "__main__":
    unittest.main()
