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

    def test_publishes_the_delay_estimate_from_the_trains_own_histogram(self):
        self.put_metrics_item({
            "pk": "TRAIN#04154",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "total_viajes": 10,
            "viajes_bucket_puntual": 2, "viajes_bucket_leve": 3,
            "viajes_bucket_significativo": 3, "viajes_bucket_grave": 2,
            "suma_retraso_significativo_minutos": 120,
            # Muestra equivalente: [0, 0, 2, 2, 6, 6, 6, 12, 20, 45].
            "histograma_retraso": {"0": 2, "2": 2, "6": 3, "12": 1, "20": 1, "45": 1},
            "last_aggregated_date": "2026-01-06",
        })

        response = self.handler.get_train_metrics_handler({}, FakeContext())
        estimate = json.loads(response["body"])[0]["estimacion_retraso"]

        self.assertEqual(estimate["mediana_minutos"], 6)
        self.assertEqual(estimate["p25_minutos"], 2)
        self.assertEqual(estimate["p75_minutos"], 12)
        self.assertEqual(estimate["p90_minutos"], 20)
        self.assertEqual(estimate["viajes_estimacion"], 10)
        self.assertEqual(estimate["base"], "tren")

    def test_train_below_min_sample_inherits_the_estimate_of_its_sentido(self):
        # 04154 tiene muestra de sobra; 04254, del mismo sentido, solo 2
        # viajes: por debajo de DELAY_ESTIMATE_MIN_SAMPLE su propia mediana
        # sería ruido, así que hereda la del sentido (que suma ambos).
        self.put_metrics_item({
            "pk": "TRAIN#04154",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "total_viajes": 10,
            "viajes_bucket_puntual": 10, "viajes_bucket_leve": 0,
            "viajes_bucket_significativo": 0, "viajes_bucket_grave": 0,
            "suma_retraso_significativo_minutos": 0,
            "histograma_retraso": {"3": 10},
            "last_aggregated_date": "2026-01-06",
        })
        self.put_metrics_item({
            "pk": "TRAIN#04254",
            "cod_comercial": "04254",
            "sentido": "Madrid",
            "total_viajes": 2,
            "viajes_bucket_puntual": 0, "viajes_bucket_leve": 0,
            "viajes_bucket_significativo": 0, "viajes_bucket_grave": 2,
            "suma_retraso_significativo_minutos": 180,
            "histograma_retraso": {"90": 2},
            "last_aggregated_date": "2026-01-06",
        })

        response = self.handler.get_train_metrics_handler({}, FakeContext())
        by_cod = {t["cod_comercial"]: t for t in json.loads(response["body"])}

        self.assertEqual(by_cod["04154"]["estimacion_retraso"]["base"], "tren")
        self.assertEqual(by_cod["04154"]["estimacion_retraso"]["mediana_minutos"], 3)

        heredada = by_cod["04254"]["estimacion_retraso"]
        self.assertEqual(heredada["base"], "sentido")
        self.assertEqual(heredada["mediana_minutos"], 3)          # domina el histograma de 04154
        self.assertEqual(heredada["viajes_estimacion"], 12)       # 10 + 2, todo el sentido Madrid

    def test_sentido_fallback_does_not_mix_directions(self):
        self.put_metrics_item({
            "pk": "TRAIN#04475",
            "cod_comercial": "04475",
            "sentido": "Galicia",
            "total_viajes": 9,
            "viajes_bucket_puntual": 9, "viajes_bucket_leve": 0,
            "viajes_bucket_significativo": 0, "viajes_bucket_grave": 0,
            "suma_retraso_significativo_minutos": 0,
            "histograma_retraso": {"1": 9},
            "last_aggregated_date": "2026-01-06",
        })
        self.put_metrics_item({
            "pk": "TRAIN#04154",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "total_viajes": 1,
            "viajes_bucket_puntual": 0, "viajes_bucket_leve": 0,
            "viajes_bucket_significativo": 1, "viajes_bucket_grave": 0,
            "suma_retraso_significativo_minutos": 40,
            "histograma_retraso": {"40": 1},
            "last_aggregated_date": "2026-01-06",
        })

        response = self.handler.get_train_metrics_handler({}, FakeContext())
        by_cod = {t["cod_comercial"]: t for t in json.loads(response["body"])}

        # Madrid solo tiene 1 viaje en total: ni propio ni por sentido llega
        # al mínimo, pero el fallback usa lo que hay de SU sentido, nunca el
        # histograma de Galicia.
        self.assertEqual(by_cod["04154"]["estimacion_retraso"]["mediana_minutos"], 40)
        self.assertEqual(by_cod["04154"]["estimacion_retraso"]["viajes_estimacion"], 1)

    def test_estimate_is_none_for_items_without_histogram(self):
        # Items agregados antes de que metrics_writer empezase a acumular el
        # histograma (y antes de correr scripts/backfill_delay_histograms.py):
        # el resto de métricas siguen sirviéndose con normalidad.
        self.put_metrics_item({
            "pk": "TRAIN#04154",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "total_viajes": 10,
            "viajes_bucket_puntual": 2, "viajes_bucket_leve": 3,
            "viajes_bucket_significativo": 3, "viajes_bucket_grave": 2,
            "suma_retraso_significativo_minutos": 120,
            "last_aggregated_date": "2026-01-06",
        })

        response = self.handler.get_train_metrics_handler({}, FakeContext())
        train = json.loads(response["body"])[0]

        self.assertIsNone(train["estimacion_retraso"])
        self.assertEqual(train["pct_retraso_significativo"], 50.0)

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
            "histograma_retraso": {"0": 1, "7": 1, "20": 1},
            "last_aggregated_date": "2026-01-06",
        })

        response = self.handler.get_train_metrics_handler({}, FakeContext())
        body = json.loads(response["body"])

        self.assertIsInstance(body[0]["estimacion_retraso"]["mediana_minutos"], int)
        self.assertIsInstance(body[0]["estimacion_retraso"]["viajes_estimacion"], int)
        self.assertIsInstance(body[0]["total_viajes"], int)
        self.assertIsInstance(body[0]["viajes_bucket_significativo"], int)
        self.assertIsInstance(body[0]["viajes_retraso_significativo"], int)
        self.assertIsInstance(body[0]["suma_retraso_significativo_minutos"], int)
        self.assertIsInstance(body[0]["pct_retraso_significativo"], float)
        self.assertIsInstance(body[0]["pct_bucket_puntual"], float)
        self.assertIsInstance(body[0]["rank_retraso"], int)


if __name__ == "__main__":
    unittest.main()
