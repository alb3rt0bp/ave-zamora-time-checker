import json
import unittest

from tests.dummies.api_handler_test_case import ApiHandlerTestCase


class FakeContext:
    aws_request_id = "get-train-schedule-test"


class TestGetTrainScheduleHandler(ApiHandlerTestCase):
    def test_returns_schedule_for_every_train_in_the_fixture(self):
        response = self.handler.get_train_schedule_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        by_cod = {t["cod_comercial"]: t for t in body}

        # tests/dummies/train_schedules_sample.json: M100/G100 (laborable), M200/G200 (domingo).
        self.assertEqual(set(by_cod), {"M100", "G100", "M200", "G200"})
        self.assertEqual(by_cod["M100"]["sentido"], "Madrid")
        self.assertEqual(by_cod["M100"]["weekdays"], [0, 1, 2, 3, 4])
        self.assertEqual(by_cod["G200"]["sentido"], "Galicia")
        self.assertEqual(by_cod["G200"]["weekdays"], [6])

    def test_sorted_by_cod_comercial(self):
        response = self.handler.get_train_schedule_handler({}, FakeContext())
        body = json.loads(response["body"])

        self.assertEqual([t["cod_comercial"] for t in body], sorted(t["cod_comercial"] for t in body))

    def test_union_of_weekdays_across_multiple_schedule_rows(self):
        # _build_train_schedule_index es una función pura: se prueba
        # directamente con datos sintéticos (un tren con una fila laborable
        # y otra domingo), sin depender del fixture cargado como
        # SCHEDULES_FILE en este proceso de test.
        trains = [
            {"cod_comercial": "X1", "sentido": "Madrid", "tipo_dia": "laborable", "weekdays": [0, 1, 2, 3, 4]},
            {"cod_comercial": "X1", "sentido": "Madrid", "tipo_dia": "domingo", "weekdays": [6]},
        ]

        index = self.handler._build_train_schedule_index(trains)

        self.assertEqual(index, [{"cod_comercial": "X1", "sentido": "Madrid", "weekdays": [0, 1, 2, 3, 4, 6]}])


if __name__ == "__main__":
    unittest.main()
