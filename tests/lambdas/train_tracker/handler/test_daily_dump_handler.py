import json
import unittest
from datetime import date
from unittest.mock import patch

from tests.dummies.handler_test_case import HandlerTestCase
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.time_utils import madrid_time_to_utc

# El dump corre a la 01:00, tras el tramo de madrugada, y vuelca el día ANTERIOR.
DUMP_RUN_DAY = date(2026, 1, 6)  # martes
TARGET_DAY = date(2026, 1, 5)    # lunes (el día que se vuelca)


class FakeContext:
    aws_request_id = "daily-dump-test"


class TestDailyDumpHandler(HandlerTestCase):
    def setUp(self):
        super().setUp()
        # El volcado exige el marcador SEED# del día como prueba de que el
        # estado que va a leer es el que se acumuló ese día (ver
        # _check_seed_marker). Los tests que prueban su ausencia lo borran.
        self._put_seed_marker(seeded_at=f"{TARGET_DAY.isoformat()}T07:00:00+01:00")

    def _put_seed_marker(self, seeded_at=None, fecha=TARGET_DAY):
        item = {"pk": f"SEED#{fecha.isoformat()}", "ttl": 0}
        if seeded_at is not None:
            item["seeded_at"] = seeded_at
        self.table.put_item(Item=item)

    def _delete_seed_marker(self, fecha=TARGET_DAY):
        self.table.delete_item(Key={"pk": f"SEED#{fecha.isoformat()}"})

    def _frozen(self):
        return make_frozen_datetime(madrid_time_to_utc(DUMP_RUN_DAY, 1, 0))

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
        # El marcador (sembrado en setUp) no es un tren: no debe volcarse.
        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 0)

    def test_follows_pagination_across_multiple_scan_pages(self):
        self.table.put_item(Item={
            "pk": f"M100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "M100",
            "sentido": "Madrid",
            "tipo_dia": "laborable",
            "hora_programada": "08:30",
            "ult_retraso": 0,
            "entregado": True,
        })
        self.table.put_item(Item={
            "pk": f"G100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "G100",
            "sentido": "Galicia",
            "tipo_dia": "laborable",
            "hora_programada": "09:30",
            "ult_retraso": 0,
            "entregado": True,
        })

        real_scan = self.handler.state_table.scan
        first_resp = real_scan(FilterExpression="attribute_exists(cod_comercial)")
        # Fuerza una segunda página devolviendo los items de a uno.
        first_page = {"Items": first_resp["Items"][:1], "LastEvaluatedKey": {"pk": "fake"}}
        second_page = {"Items": first_resp["Items"][1:]}

        with patch.object(self.handler.state_table, "scan", side_effect=[first_page, second_page]) as mock_scan:
            with patch("handler.datetime", self._frozen()):
                result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(mock_scan.call_count, 2)
        self.assertEqual(mock_scan.call_args_list[1].kwargs["ExclusiveStartKey"], {"pk": "fake"})
        self.assertEqual(result["written"], 2)

    def test_metrics_writer_failure_does_not_fail_dump(self):
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

        with patch("handler.MetricsWriter", side_effect=Exception("boom")):
            with patch("handler.datetime", self._frozen()):
                result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 1)
        self.assertIn("key", result)

    def test_aborts_without_writing_when_the_seed_marker_is_missing(self):
        # Regresión del 2026-09-18: el TTL barrió el estado del día (marcador
        # incluido) antes del volcado y el tramo de madrugada resembró
        # placeholders, así que el volcado registró el día entero como
        # cancelado. Sin marcador el estado no es fiable: no se escribe nada.
        self._delete_seed_marker()
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

        self.assertEqual(result["statusCode"], 500)
        self.assertEqual(result["reason"], "seed_marker_missing")
        self.assertNotIn("Contents", self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET))

    def test_alerts_when_the_seed_marker_is_missing(self):
        self._delete_seed_marker()
        self.table.put_item(Item={
            "pk": f"G100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "G100", "sentido": "Galicia", "tipo_dia": "laborable",
            "hora_programada": "09:30", "ult_retraso": 0, "entregado": False,
        })

        with patch("handler.datetime", self._frozen()):
            self.handler.daily_dump_handler({}, FakeContext())

        alerts = self.get_published_data_quality_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertIn("estado del día perdido", alerts[0]["subject"])

    def test_aborts_when_the_day_was_reseeded_afterwards(self):
        # Marcador escrito en el día del volcado, no en el día volcado: el
        # día se resembró a posteriori y sus trenes son placeholders nuevos.
        self._delete_seed_marker()
        self._put_seed_marker(seeded_at=f"{DUMP_RUN_DAY.isoformat()}T01:05:00+01:00")
        self.table.put_item(Item={
            "pk": f"G100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "G100", "sentido": "Galicia", "tipo_dia": "laborable",
            "hora_programada": "09:30", "ult_retraso": 0, "entregado": False,
        })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["reason"], "seed_marker_rebuilt")
        self.assertNotIn("Contents", self.s3.list_objects_v2(Bucket=self.handler.S3_BUCKET))
        self.assertIn("resembrado", self.get_published_data_quality_alerts()[0]["subject"])

    def test_accepts_a_legacy_marker_without_seeded_at(self):
        # Los marcadores escritos por versiones anteriores no llevan
        # 'seeded_at': solo se puede comprobar que existen, y se dan por buenos.
        self._delete_seed_marker()
        self._put_seed_marker(seeded_at=None)
        self.table.put_item(Item={
            "pk": f"M100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable",
            "hora_programada": "08:30", "hora_llegada_corregida": "08:35",
            "ult_retraso": 5, "entregado": True,
        })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 1)

    def test_alerts_when_too_many_trains_are_cancelled_but_still_writes(self):
        # Una huelga real puede dar un porcentaje altísimo de cancelados y es
        # un dato legítimo: el fichero se escribe igual, pero avisa.
        for cod in ("M100", "M200", "G100"):
            self.table.put_item(Item={
                "pk": f"{cod}#{TARGET_DAY.isoformat()}",
                "cod_comercial": cod, "sentido": "Madrid", "tipo_dia": "laborable",
                "hora_programada": "08:30", "ult_retraso": 0, "entregado": False,
            })

        with patch("handler.datetime", self._frozen()):
            result = self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(result["written"], 3)
        alerts = self.get_published_data_quality_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertIn("cancelados", alerts[0]["subject"])

    def test_does_not_alert_on_a_normal_day(self):
        self.table.put_item(Item={
            "pk": f"M100#{TARGET_DAY.isoformat()}",
            "cod_comercial": "M100", "sentido": "Madrid", "tipo_dia": "laborable",
            "hora_programada": "08:30", "hora_llegada_corregida": "08:35",
            "ult_retraso": 5, "entregado": True,
        })

        with patch("handler.datetime", self._frozen()):
            self.handler.daily_dump_handler({}, FakeContext())

        self.assertEqual(self.get_published_data_quality_alerts(), [])

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
