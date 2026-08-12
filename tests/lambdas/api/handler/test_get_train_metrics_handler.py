import json
import unittest

from tests.dummies.api_handler_test_case import ApiHandlerTestCase


class FakeContext:
    aws_request_id = "get-train-metrics-test"


class TestGetTrainMetricsHandler(ApiHandlerTestCase):
    def test_returns_empty_list_when_no_metrics_yet(self):
        response = self.handler.get_train_metrics_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), [])

    def test_returns_buckets_percentages_and_ranking_across_trains(self):
        self.put_metrics_item({
            "pk": "TRAIN#04154",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "total_viajes": 10,
            # 3 significativo + 2 grave = 5/10 = 50% de retraso significativo
            "viajes_bucket_puntual": 2, "viajes_bucket_leve": 3,
            "viajes_bucket_significativo": 3, "viajes_bucket_grave": 2,
            "suma_retraso_significativo_minutos": 120,
            "last_aggregated_date": "2026-01-06",
        })
        self.put_metrics_item({
            "pk": "TRAIN#04475",
            "cod_comercial": "04475",
            "sentido": "Galicia",
            "total_viajes": 20,
            # 1 significativo + 1 grave = 2/20 = 10% de retraso significativo
            "viajes_bucket_puntual": 10, "viajes_bucket_leve": 8,
            "viajes_bucket_significativo": 1, "viajes_bucket_grave": 1,
            "suma_retraso_significativo_minutos": 40,
            "last_aggregated_date": "2026-01-06",
        })

        response = self.handler.get_train_metrics_handler({}, FakeContext())
        body = json.loads(response["body"])

        self.assertEqual(len(body), 2)
        by_cod = {t["cod_comercial"]: t for t in body}

        self.assertEqual(by_cod["04154"]["pct_retraso_significativo"], 50.0)
        self.assertEqual(by_cod["04154"]["viajes_retraso_significativo"], 5)
        self.assertEqual(by_cod["04154"]["viajes_bucket_puntual"], 2)
        self.assertEqual(by_cod["04154"]["pct_bucket_leve"], 30.0)
        self.assertEqual(by_cod["04154"]["rank_retraso"], 1)  # más propenso a retrasarse

        self.assertEqual(by_cod["04475"]["pct_retraso_significativo"], 10.0)
        self.assertEqual(by_cod["04475"]["rank_retraso"], 2)

        for train in body:
            self.assertEqual(train["total_trenes_comparados"], 2)

    def test_response_numbers_are_real_json_numbers_not_strings(self):
        # Regresión: DynamoDB devuelve Decimal, y _json_response usa
        # json.dumps(default=str) — sin castear explícitamente, los números
        # saldrían como strings entrecomillados en el JSON.
        self.put_metrics_item({
            "pk": "TRAIN#04154",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "total_viajes": 3,
            "viajes_bucket_puntual": 1, "viajes_bucket_leve": 1,
            "viajes_bucket_significativo": 1, "viajes_bucket_grave": 0,
            "suma_retraso_significativo_minutos": 20,
            "last_aggregated_date": "2026-01-06",
        })

        response = self.handler.get_train_metrics_handler({}, FakeContext())
        body = json.loads(response["body"])

        self.assertIsInstance(body[0]["total_viajes"], int)
        self.assertIsInstance(body[0]["viajes_bucket_significativo"], int)
        self.assertIsInstance(body[0]["viajes_retraso_significativo"], int)
        self.assertIsInstance(body[0]["suma_retraso_significativo_minutos"], int)
        self.assertIsInstance(body[0]["pct_retraso_significativo"], float)
        self.assertIsInstance(body[0]["pct_bucket_puntual"], float)
        self.assertIsInstance(body[0]["rank_retraso"], int)


if __name__ == "__main__":
    unittest.main()
