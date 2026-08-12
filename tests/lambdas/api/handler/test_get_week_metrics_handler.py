import json
import unittest
from datetime import date
from unittest.mock import patch

from tests.dummies.api_handler_test_case import ApiHandlerTestCase
from tests.dummies.frozen_datetime import make_frozen_datetime
from tests.dummies.time_utils import madrid_time_to_utc

WEEK_ITEM = {
    "pk": "WEEK#2026-W02",
    "iso_year": 2026,
    "iso_week": 2,
    "week_start": "2026-01-05",
    "week_end": "2026-01-11",
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
        # lunes: 3/10 = 30% pero el recuento más alto (3 retrasos)
        "0": {"total_viajes": 10, "viajes_retraso_significativo": 3, "suma_retraso_significativo_minutos": 45},
        # martes: 2/2 = 100%, la tasa más alta, aunque solo 2 retrasos
        "1": {"total_viajes": 2, "viajes_retraso_significativo": 2, "suma_retraso_significativo_minutos": 50},
    },
    "last_aggregated_date": "2026-01-06",
}


class FakeContext:
    aws_request_id = "get-week-metrics-test"


class TestGetWeekMetricsHandler(ApiHandlerTestCase):
    def test_returns_empty_list_when_no_metrics_yet(self):
        response = self.handler.get_week_metrics_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), [])

    def test_derives_percentages_and_extremes(self):
        self.put_metrics_item(dict(WEEK_ITEM))

        # "Hoy" dentro de la semana (jueves 2026-01-08): todavía en curso.
        frozen = make_frozen_datetime(madrid_time_to_utc(date(2026, 1, 8), 10, 0))
        with patch("api_handler.datetime", frozen):
            response = self.handler.get_week_metrics_handler({}, FakeContext())

        body = json.loads(response["body"])
        self.assertEqual(len(body), 1)
        week = body[0]

        self.assertEqual(week["iso_year"], 2026)
        self.assertEqual(week["iso_week"], 2)
        self.assertFalse(week["is_complete"])

        self.assertAlmostEqual(week["pct_retraso_significativo"], 41.67, places=2)  # 5/12
        self.assertEqual(week["viajes_bucket_puntual"], 3)
        self.assertAlmostEqual(week["pct_bucket_leve"], 33.33, places=2)  # 4/12

        self.assertEqual(week["tren_mas_probable"]["cod_comercial"], "04475")
        self.assertEqual(week["tren_menos_probable"]["cod_comercial"], "04154")

        self.assertEqual(week["dia_semana_con_mas_retrasos"]["dia_semana"], 0)   # lunes: más retrasos en bruto
        self.assertEqual(week["dia_semana_mas_probable"]["dia_semana"], 1)       # martes: mayor tasa
        self.assertEqual(week["dia_semana_menos_probable"]["dia_semana"], 0)     # lunes: menor tasa

    def test_is_complete_once_week_end_has_passed(self):
        self.put_metrics_item(dict(WEEK_ITEM))

        # "Hoy" ya pasado el domingo de cierre (2026-01-11): semana completa.
        frozen = make_frozen_datetime(madrid_time_to_utc(date(2026, 1, 13), 10, 0))
        with patch("api_handler.datetime", frozen):
            response = self.handler.get_week_metrics_handler({}, FakeContext())

        body = json.loads(response["body"])
        self.assertTrue(body[0]["is_complete"])

    def test_weeks_are_sorted_ascending(self):
        self.put_metrics_item({**WEEK_ITEM, "pk": "WEEK#2026-W05", "iso_year": 2026, "iso_week": 5,
                                "week_start": "2026-01-26", "week_end": "2026-02-01"})
        self.put_metrics_item(dict(WEEK_ITEM))  # W02

        frozen = make_frozen_datetime(madrid_time_to_utc(date(2026, 2, 2), 10, 0))
        with patch("api_handler.datetime", frozen):
            response = self.handler.get_week_metrics_handler({}, FakeContext())

        body = json.loads(response["body"])
        self.assertEqual([w["iso_week"] for w in body], [2, 5])


if __name__ == "__main__":
    unittest.main()
