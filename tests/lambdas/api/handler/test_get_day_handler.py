import json
import unittest

from tests.dummies.api_handler_test_case import ApiHandlerTestCase

PAST_DATE_ISO = "2026-01-04"
PAST_DATE_KEY = "zamora-trains/year=2026/month=01/day=04/2026-01-04.jsonl"


class FakeContext:
    aws_request_id = "get-day-test"


class TestGetDayHandler(ApiHandlerTestCase):
    def test_returns_parsed_jsonl_records_for_dumped_day(self):
        self.put_daily_jsonl(PAST_DATE_KEY, [
            {
                "event_id": "04154-2026-01-04T07:41",
                "cod_comercial": "04154",
                "sentido": "Madrid",
                "tipo_dia": "domingo",
                "dia_semana": "Sunday",
                "hora_programada": "07:41",
                "hora_llegada_corregida": "07:47",
                "minutos_retraso": 6,
                "cancelado": False,
            },
        ])
        event = {"pathParameters": {"date": PAST_DATE_ISO}}

        response = self.handler.get_day_handler(event, FakeContext())

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["cod_comercial"], "04154")
        self.assertEqual(body[0]["minutos_retraso"], 6)

    def test_skips_blank_lines_in_jsonl_body(self):
        self.s3.put_object(
            Bucket=self.handler.S3_BUCKET,
            Key=PAST_DATE_KEY,
            Body=b'{"cod_comercial": "04154"}\n\n{"cod_comercial": "04475"}\n',
            ContentType="application/x-ndjson",
        )
        event = {"pathParameters": {"date": PAST_DATE_ISO}}

        response = self.handler.get_day_handler(event, FakeContext())

        body = json.loads(response["body"])
        self.assertEqual([r["cod_comercial"] for r in body], ["04154", "04475"])

    def test_returns_404_when_day_not_dumped_yet(self):
        event = {"pathParameters": {"date": PAST_DATE_ISO}}

        response = self.handler.get_day_handler(event, FakeContext())

        self.assertEqual(response["statusCode"], 404)

    def test_returns_400_for_malformed_date(self):
        event = {"pathParameters": {"date": "not-a-date"}}

        response = self.handler.get_day_handler(event, FakeContext())

        self.assertEqual(response["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
