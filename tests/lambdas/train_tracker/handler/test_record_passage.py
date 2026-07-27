import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.reference_dates import MONDAY

from datalake_writer import DatalakeWriter

TZ = ZoneInfo("Europe/Madrid")
NOW = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 8, 45, tzinfo=TZ)

SCHEDULED = {
    "cod_comercial": "M100",
    "sentido": "Madrid",
    "tipo_dia": "laborable",
    "hora_llegada_destino": "08:30",
}

LIVE = {"codEstAnt": "17000", "codEstSig": "", "ultRetraso": 12}


class TestRecordPassage(HandlerTestCase):
    def setUp(self):
        super().setUp()
        self.writer = DatalakeWriter(self.s3, self.handler.S3_BUCKET, SAMPLE_LOG_EXTRA)

    def _get_only_object_body(self):
        listed = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)["Contents"]
        self.assertEqual(len(listed), 1)
        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=listed[0]["Key"])["Body"].read()
        return json.loads(body)

    def test_writes_record_with_expected_fields(self):
        self.handler._record_passage(SCHEDULED, LIVE, NOW, SAMPLE_LOG_EXTRA, self.writer)

        record = self._get_only_object_body()
        self.assertEqual(record["cod_comercial"], "M100")
        self.assertEqual(record["sentido"], "Madrid")
        self.assertEqual(record["hora_programada"], "08:30")
        self.assertEqual(record["hora_real"], "08:42")  # 08:30 + 12 min
        self.assertEqual(record["minutos_retraso"], 12)
        self.assertEqual(record["cod_est_ant"], "17000")
        self.assertEqual(record["ult_retraso_renfe"], 12)

    def test_capturado_en_zamora_defaults_to_false(self):
        self.handler._record_passage(SCHEDULED, LIVE, NOW, SAMPLE_LOG_EXTRA, self.writer)

        record = self._get_only_object_body()
        self.assertFalse(record["capturado_en_zamora"])

    def test_capturado_en_zamora_can_be_set_true(self):
        self.handler._record_passage(
            SCHEDULED, LIVE, NOW, SAMPLE_LOG_EXTRA, self.writer, capturado_en_zamora=True
        )

        record = self._get_only_object_body()
        self.assertTrue(record["capturado_en_zamora"])


if __name__ == "__main__":
    unittest.main()
