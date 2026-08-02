import json
import unittest
from datetime import date
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.time_utils import madrid_time_to_utc

# El dump corre poco después de medianoche y vuelca el día ANTERIOR.
DUMP_RUN_DAY = date(2026, 1, 6)  # martes
TARGET_DAY = date(2026, 1, 5)    # lunes (el día que se vuelca)


class FakeContext:
    aws_request_id = "daily-dump-test"


class TestDailyDumpHandler(HandlerTestCase):
    def _frozen(self):
        return make_frozen_datetime(madrid_time_to_utc(DUMP_RUN_DAY, 0, 15))

    def test_no_records_writes_nothing(self):
        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result, {"statusCode": 200, "written": 0})
        objects = self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET)
        self.assertNotIn("Contents", objects)

    def test_writes_one_file_with_entregado_trains_of_target_day(self):
        self.table.put_item(Item={
            "pk": f"M100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "08:30",
            "hora_llegada_corregida": "08:35",
            "hora_paso_zamora": "07:03",
            "ult_retraso": 5,
            "entregado": True,
        })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 1)
        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=result["key"])["Body"].read()
        record = json.loads(body.decode("utf-8").strip())
        self.assertEqual(record["cod_comercial"], "M100")
        self.assertEqual(record["hora_programada"], "08:30")
        self.assertEqual(record["hora_llegada_corregida"], "08:35")
        self.assertEqual(record["hora_paso_zamora"], "07:03")
        self.assertEqual(record["minutos_retraso"], 5)
        self.assertFalse(record["cancelado"])

    def test_writes_never_entregado_train_as_cancelado_with_null_delay(self):
        # Tren nunca detectado en flotaLD.json en todo el día (p. ej. huelga):
        # se vuelca igualmente, pero sin fabricar un retraso de 0.
        self.table.put_item(Item={
            "pk": f"G100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "G100",
            "sentido": "Galicia",
            "tipo_dia": "laborable",
            "hora_programada": "09:30",
            "ult_retraso": 0,
            "entregado": False,
        })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 1)
        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=result["key"])["Body"].read()
        record = json.loads(body.decode("utf-8").strip())
        self.assertEqual(record["cod_comercial"], "G100")
        self.assertTrue(record["cancelado"])
        self.assertIsNone(record["minutos_retraso"])
        self.assertIsNone(record["hora_llegada_corregida"])
        self.assertIsNone(record["hora_paso_zamora"])

    def test_writes_gtfsrt_fields_when_entregado(self):
        self.table.put_item(Item={
            "pk": f"M100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "08:30",
            "hora_llegada_corregida": "08:35",
            "hora_paso_zamora": "07:03",
            "ult_retraso": 5,
            "minutos_retraso_gtfsrt": 4,
            "hora_llegada_gtfsrt": "08:34",
            "hora_paso_zamora_gtfsrt": "07:02",
            "entregado": True,
        })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=result["key"])["Body"].read()
        record = json.loads(body.decode("utf-8").strip())
        self.assertEqual(record["minutos_retraso_gtfsrt"], 4)
        self.assertEqual(record["hora_llegada_gtfsrt"], "08:34")
        self.assertEqual(record["hora_paso_zamora_gtfsrt"], "07:02")

    def test_gtfsrt_fields_are_null_when_not_entregado(self):
        self.table.put_item(Item={
            "pk": f"G100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "G100",
            "sentido": "Galicia",
            "tipo_dia": "laborable",
            "hora_programada": "09:30",
            "ult_retraso": 0,
            "entregado": False,
        })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        body = self.s3.get_object(Bucket=self.handler.S3_BUCKET, Key=result["key"])["Body"].read()
        record = json.loads(body.decode("utf-8").strip())
        self.assertIsNone(record["minutos_retraso_gtfsrt"])
        self.assertIsNone(record["hora_llegada_gtfsrt"])
        self.assertIsNone(record["hora_paso_zamora_gtfsrt"])

    def test_excludes_seed_marker_item(self):
        self.table.put_item(Item={"pk": f"SEED#{TARGET_DAY.isoformat()}", "ttl": 0})

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 0)

    def test_excludes_entregado_trains_from_a_different_day(self):
        self.table.put_item(Item={
            "pk": f"M100#2026-01-04",
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "08:30",
            "ult_retraso": 0,
            "entregado": True,
        })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 0)


if __name__ == "__main__":
    unittest.main()
