import json
import unittest

from tests.dummies.api_handler_test_case import ApiHandlerTestCase

GLOBAL_ITEM = {
    "pk": "GLOBAL",
    "total_viajes": 12,
    # 3 significativo + 2 grave = 5/12 = 41.67% de retraso significativo
    "viajes_bucket_puntual": 3, "viajes_bucket_leve": 4,
    "viajes_bucket_significativo": 3, "viajes_bucket_grave": 2,
    "suma_retraso_significativo_minutos": 95,
    "por_dia_semana": {
        # martes: 2/2 = 100%, la tasa más alta
        "1": {"total_viajes": 2, "viajes_retraso_significativo": 2, "suma_retraso_significativo_minutos": 50},
        # lunes: 3/10 = 30%
        "0": {"total_viajes": 10, "viajes_retraso_significativo": 3, "suma_retraso_significativo_minutos": 45},
    },
    "por_franja_horaria": {
        # mañana: 2/8 = 25%
        "manana": {"total_viajes": 8, "viajes_retraso_significativo": 2, "suma_retraso_significativo_minutos": 30},
        # noche: 3/4 = 75%, la tasa más alta
        "noche": {"total_viajes": 4, "viajes_retraso_significativo": 3, "suma_retraso_significativo_minutos": 65},
    },
    "first_aggregated_date": "2026-07-31",
    "last_aggregated_date": "2026-08-10",
}


class FakeContext:
    aws_request_id = "get-global-metrics-test"


class TestGetGlobalMetricsHandler(ApiHandlerTestCase):
    def test_returns_404_when_no_global_metrics_yet(self):
        response = self.handler.get_global_metrics_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 404)

    def test_returns_buckets_and_extremes(self):
        self.put_metrics_item(dict(GLOBAL_ITEM))
        self.put_metrics_item({
            "pk": "TRAIN#04154",
            "cod_comercial": "04154",
            "sentido": "Madrid",
            "total_viajes": 10,
            "viajes_bucket_puntual": 2, "viajes_bucket_leve": 3,
            "viajes_bucket_significativo": 3, "viajes_bucket_grave": 2,
            "suma_retraso_significativo_minutos": 120,
            "last_aggregated_date": "2026-08-10",
        })
        # Segundo tren, con menos retraso, para distinguir tren_menos_probable
        # de tren_mas_probable (con uno solo, ambos apuntarían al mismo).
        self.put_metrics_item({
            "pk": "TRAIN#04505",
            "cod_comercial": "04505",
            "sentido": "Galicia",
            "total_viajes": 10,
            "viajes_bucket_puntual": 9, "viajes_bucket_leve": 1,
            "viajes_bucket_significativo": 0, "viajes_bucket_grave": 0,
            "suma_retraso_significativo_minutos": 0,
            "last_aggregated_date": "2026-08-10",
        })

        response = self.handler.get_global_metrics_handler({}, FakeContext())
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])

        self.assertEqual(body["total_viajes"], 12)
        self.assertAlmostEqual(body["pct_retraso_significativo"], 41.67, places=2)
        self.assertEqual(body["viajes_bucket_puntual"], 3)
        self.assertEqual(body["first_aggregated_date"], "2026-07-31")
        self.assertEqual(body["significant_delay_threshold_minutes"], 15)

        self.assertEqual(body["dia_semana_mas_probable"]["dia_semana"], 1)   # martes: 100%
        self.assertEqual(body["dia_semana_menos_probable"]["dia_semana"], 0)  # lunes: 30%
        self.assertEqual(body["franja_horaria_mas_probable"]["franja"], "noche")  # 75%
        self.assertEqual(body["tren_mas_probable"]["cod_comercial"], "04154")
        self.assertEqual(body["tren_mas_probable"]["rank_retraso"], 1)
        self.assertEqual(body["tren_menos_probable"]["cod_comercial"], "04505")

        # Regresión Decimal→string (ver test_get_train_metrics_handler.py).
        self.assertIsInstance(body["total_viajes"], int)
        self.assertIsInstance(body["pct_retraso_significativo"], float)


if __name__ == "__main__":
    unittest.main()
