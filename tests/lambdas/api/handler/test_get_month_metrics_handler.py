import json
import unittest
from datetime import date
from unittest.mock import patch

from tests.dummies.api_handler_test_case import ApiHandlerTestCase
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.time_utils import madrid_time_to_utc

MONTH_ITEM = {
    "pk": "MONTH#2026-01",
    "year": 2026,
    "month": 1,
    "total_viajes": 12,
    # 3 significativo + 2 grave = 5/12 = 41.67% de retraso significativo
    "viajes_bucket_puntual": 3, "viajes_bucket_leve": 4,
    "viajes_bucket_significativo": 3, "viajes_bucket_grave": 2,
    "suma_retraso_significativo_minutos": 95,
    "por_tren": {
        # 3/8 = 37.5% — menos probable
        "04154": {"total_viajes": 8, "viajes_retraso_significativo": 3, "suma_retraso_significativo_minutos": 45},
        # 2/4 = 50% — más probable
        "04475": {"total_viajes": 4, "viajes_retraso_significativo": 2, "suma_retraso_significativo_minutos": 50},
    },
    "por_dia_semana": {
        # lunes (4 ocurrencias en el mes): 3/10 = 30% pero el recuento más alto
        "0": {"total_viajes": 10, "viajes_retraso_significativo": 3, "suma_retraso_significativo_minutos": 45},
        # martes (1 ocurrencia): 2/2 = 100%, la tasa más alta
        "1": {"total_viajes": 2, "viajes_retraso_significativo": 2, "suma_retraso_significativo_minutos": 50},
    },
    "last_aggregated_date": "2026-01-06",
}


class FakeContext:
    aws_request_id = "get-month-metrics-test"


class TestGetMonthMetricsHandler(ApiHandlerTestCase):
    def test_returns_empty_list_when_no_metrics_yet(self):
        response = self.handler.get_month_metrics_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), [])

    def test_derives_percentages_and_extremes(self):
        self.put_metrics_item(dict(MONTH_ITEM))

        # "Hoy" dentro del mes: todavía en curso.
        frozen = make_frozen_datetime(madrid_time_to_utc(date(2026, 1, 15), 10, 0))
        with patch("api_handler.datetime", frozen):
            response = self.handler.get_month_metrics_handler({}, FakeContext())

        body = json.loads(response["body"])
        self.assertEqual(len(body), 1)
        month = body[0]

        self.assertEqual(month["year"], 2026)
        self.assertEqual(month["month"], 1)
        self.assertFalse(month["is_complete"])

        self.assertAlmostEqual(month["pct_retraso_significativo"], 41.67, places=2)  # 5/12
        self.assertEqual(month["viajes_bucket_puntual"], 3)
        self.assertAlmostEqual(month["pct_bucket_leve"], 33.33, places=2)  # 4/12

        self.assertEqual(month["tren_mas_probable"]["cod_comercial"], "04475")
        self.assertEqual(month["tren_menos_probable"]["cod_comercial"], "04154")

        self.assertEqual(month["dia_semana_con_mas_retrasos"]["dia_semana"], 0)   # lunes: más retrasos en bruto
        self.assertEqual(month["dia_semana_mas_probable"]["dia_semana"], 1)       # martes: mayor tasa
        self.assertEqual(month["dia_semana_menos_probable"]["dia_semana"], 0)     # lunes: menor tasa

    def test_is_complete_once_month_has_ended(self):
        self.put_metrics_item(dict(MONTH_ITEM))

        # "Hoy" ya en febrero: enero quedó completo.
        frozen = make_frozen_datetime(madrid_time_to_utc(date(2026, 2, 3), 10, 0))
        with patch("api_handler.datetime", frozen):
            response = self.handler.get_month_metrics_handler({}, FakeContext())

        body = json.loads(response["body"])
        self.assertTrue(body[0]["is_complete"])

    def test_months_are_sorted_ascending(self):
        self.put_metrics_item({**MONTH_ITEM, "pk": "MONTH#2026-03", "year": 2026, "month": 3})
        self.put_metrics_item(dict(MONTH_ITEM))  # 2026-01

        frozen = make_frozen_datetime(madrid_time_to_utc(date(2026, 3, 15), 10, 0))
        with patch("api_handler.datetime", frozen):
            response = self.handler.get_month_metrics_handler({}, FakeContext())

        body = json.loads(response["body"])
        self.assertEqual([m["month"] for m in body], [1, 3])


if __name__ == "__main__":
    unittest.main()
