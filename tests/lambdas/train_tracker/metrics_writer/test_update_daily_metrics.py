import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from tests.dummies.handler_test_case import HandlerTestCase

import metrics_writer  # noqa: E402 - requiere el sys.path que fija tests.dummies.handler_test_case

THRESHOLD_MINUTES = 15
NOW_LOCAL = datetime(2026, 1, 6, 0, 15, tzinfo=ZoneInfo("Europe/Madrid"))

MONDAY = date(2026, 1, 5)    # semana ISO 2026-W02, mes 2026-01
TUESDAY = date(2026, 1, 6)   # misma semana/mes que MONDAY

_ZERO_BUCKETS = {
    "viajes_bucket_puntual": 0,
    "viajes_bucket_leve": 0,
    "viajes_bucket_significativo": 0,
    "viajes_bucket_grave": 0,
}


def _record(cod: str, sentido: str, minutos_retraso: int, cancelado: bool = False,
            hora_paso_zamora: str | None = None) -> dict:
    return {
        "cod_comercial": cod,
        "sentido": sentido,
        "minutos_retraso": minutos_retraso,
        "cancelado": cancelado,
        "hora_paso_zamora": hora_paso_zamora,
    }


def _assert_buckets(test: unittest.TestCase, item: dict, **expected) -> None:
    """expected solo necesita listar los tramos no-cero, el resto se asume 0."""
    for key in _ZERO_BUCKETS:
        test.assertEqual(item[key], expected.get(key, 0), key)


class TestUpdateDailyMetrics(HandlerTestCase):
    def _writer(self) -> metrics_writer.MetricsWriter:
        return metrics_writer.MetricsWriter(self.metrics_table, THRESHOLD_MINUTES, {"span_id": "test"})

    def test_first_day_creates_train_and_period_items(self):
        records = [
            _record("04154", "Madrid", 20),   # tramo "significativo" (15 < 20 <= 60)
            _record("04475", "Galicia", 5),   # tramo "leve" (5 <= 5 <= 15)
        ]

        self._writer().update_daily_metrics(records, MONDAY, NOW_LOCAL)

        train_04154 = self.get_metrics_item("TRAIN#04154")
        self.assertEqual(train_04154["total_viajes"], 1)
        _assert_buckets(self, train_04154, viajes_bucket_significativo=1)
        self.assertEqual(train_04154["suma_retraso_significativo_minutos"], 20)
        self.assertEqual(train_04154["sentido"], "Madrid")
        self.assertEqual(train_04154["last_aggregated_date"], MONDAY.isoformat())

        train_04475 = self.get_metrics_item("TRAIN#04475")
        self.assertEqual(train_04475["total_viajes"], 1)
        _assert_buckets(self, train_04475, viajes_bucket_leve=1)
        self.assertEqual(train_04475["suma_retraso_significativo_minutos"], 0)

        week = self.get_metrics_item("WEEK#2026-W02")
        self.assertEqual(week["iso_year"], 2026)
        self.assertEqual(week["iso_week"], 2)
        self.assertEqual(week["week_start"], "2026-01-05")
        self.assertEqual(week["week_end"], "2026-01-11")
        self.assertEqual(week["total_viajes"], 2)
        _assert_buckets(self, week, viajes_bucket_significativo=1, viajes_bucket_leve=1)
        self.assertEqual(week["suma_retraso_significativo_minutos"], 20)
        self.assertEqual(week["por_tren"]["04154"]["total_viajes"], 1)
        self.assertEqual(week["por_tren"]["04154"]["viajes_retraso_significativo"], 1)
        self.assertEqual(week["por_dia_semana"]["0"]["total_viajes"], 2)  # lunes = weekday 0
        self.assertEqual(week["por_dia_semana"]["0"]["viajes_retraso_significativo"], 1)

        month = self.get_metrics_item("MONTH#2026-01")
        self.assertEqual(month["year"], 2026)
        self.assertEqual(month["month"], 1)
        self.assertEqual(month["total_viajes"], 2)
        _assert_buckets(self, month, viajes_bucket_significativo=1, viajes_bucket_leve=1)

    def test_delay_below_5_minutes_is_puntual(self):
        self._writer().update_daily_metrics([_record("04154", "Madrid", 2)], MONDAY, NOW_LOCAL)

        train = self.get_metrics_item("TRAIN#04154")
        _assert_buckets(self, train, viajes_bucket_puntual=1)
        self.assertEqual(train["suma_retraso_significativo_minutos"], 0)

    def test_delay_exactly_at_threshold_is_leve_not_significativo(self):
        self._writer().update_daily_metrics([_record("04154", "Madrid", THRESHOLD_MINUTES)], MONDAY, NOW_LOCAL)

        train = self.get_metrics_item("TRAIN#04154")
        self.assertEqual(train["total_viajes"], 1)
        _assert_buckets(self, train, viajes_bucket_leve=1)
        self.assertEqual(train["suma_retraso_significativo_minutos"], 0)

    def test_delay_over_60_minutes_is_grave(self):
        self._writer().update_daily_metrics([_record("04154", "Madrid", 90)], MONDAY, NOW_LOCAL)

        train = self.get_metrics_item("TRAIN#04154")
        _assert_buckets(self, train, viajes_bucket_grave=1)
        self.assertEqual(train["suma_retraso_significativo_minutos"], 90)

    def test_accumulates_across_multiple_days_in_same_week_and_month(self):
        self._writer().update_daily_metrics([_record("04154", "Madrid", 20)], MONDAY, NOW_LOCAL)
        self._writer().update_daily_metrics([_record("04154", "Madrid", 30)], TUESDAY, NOW_LOCAL)

        train = self.get_metrics_item("TRAIN#04154")
        self.assertEqual(train["total_viajes"], 2)
        _assert_buckets(self, train, viajes_bucket_significativo=2)
        self.assertEqual(train["suma_retraso_significativo_minutos"], 50)
        self.assertEqual(train["last_aggregated_date"], TUESDAY.isoformat())

        week = self.get_metrics_item("WEEK#2026-W02")
        self.assertEqual(week["total_viajes"], 2)
        self.assertEqual(week["suma_retraso_significativo_minutos"], 50)
        self.assertEqual(week["por_dia_semana"]["0"]["total_viajes"], 1)  # lunes
        self.assertEqual(week["por_dia_semana"]["1"]["total_viajes"], 1)  # martes

        month = self.get_metrics_item("MONTH#2026-01")
        self.assertEqual(month["total_viajes"], 2)
        self.assertEqual(month["suma_retraso_significativo_minutos"], 50)

    def test_retry_same_target_date_does_not_double_count(self):
        records = [_record("04154", "Madrid", 20)]
        writer = self._writer()

        writer.update_daily_metrics(records, MONDAY, NOW_LOCAL)
        writer.update_daily_metrics(records, MONDAY, NOW_LOCAL)  # reintento del mismo día

        train = self.get_metrics_item("TRAIN#04154")
        self.assertEqual(train["total_viajes"], 1)

        week = self.get_metrics_item("WEEK#2026-W02")
        self.assertEqual(week["total_viajes"], 1)

        month = self.get_metrics_item("MONTH#2026-01")
        self.assertEqual(month["total_viajes"], 1)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["total_viajes"], 1)

    def test_cancelado_records_are_excluded_entirely(self):
        records = [
            _record("04154", "Madrid", 999, cancelado=True),
            _record("04475", "Galicia", 5),
        ]

        self._writer().update_daily_metrics(records, MONDAY, NOW_LOCAL)

        self.assertIsNone(self.get_metrics_item("TRAIN#04154"))
        train_04475 = self.get_metrics_item("TRAIN#04475")
        self.assertEqual(train_04475["total_viajes"], 1)

        week = self.get_metrics_item("WEEK#2026-W02")
        self.assertEqual(week["total_viajes"], 1)
        self.assertNotIn("04154", week["por_tren"])

    def test_all_cancelado_writes_nothing(self):
        records = [_record("04154", "Madrid", 999, cancelado=True)]

        self._writer().update_daily_metrics(records, MONDAY, NOW_LOCAL)

        self.assertIsNone(self.get_metrics_item("TRAIN#04154"))
        self.assertIsNone(self.get_metrics_item("WEEK#2026-W02"))
        self.assertIsNone(self.get_metrics_item("MONTH#2026-01"))
        self.assertIsNone(self.get_metrics_item("GLOBAL"))

    def test_iso_week_spans_year_boundary_correctly(self):
        # 2025-12-29 (lunes) cae en la semana ISO 2026-W01, no en 2025.
        boundary_monday = date(2025, 12, 29)
        self._writer().update_daily_metrics([_record("04154", "Madrid", 20)], boundary_monday, NOW_LOCAL)

        week = self.get_metrics_item("WEEK#2026-W01")
        self.assertIsNotNone(week)
        self.assertEqual(week["iso_year"], 2026)
        self.assertEqual(week["iso_week"], 1)
        self.assertEqual(week["week_start"], "2025-12-29")

        # El mes natural, en cambio, sigue siendo diciembre de 2025.
        month = self.get_metrics_item("MONTH#2025-12")
        self.assertIsNotNone(month)
        self.assertEqual(month["total_viajes"], 1)

    # ── GLOBAL ────────────────────────────────────────────────────────────

    def test_global_item_created_with_buckets_and_first_aggregated_date(self):
        records = [
            _record("04154", "Madrid", 20, hora_paso_zamora="07:30"),
            _record("04475", "Galicia", 5, hora_paso_zamora="15:00"),
        ]

        self._writer().update_daily_metrics(records, MONDAY, NOW_LOCAL)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["total_viajes"], 2)
        _assert_buckets(self, glob, viajes_bucket_significativo=1, viajes_bucket_leve=1)
        self.assertEqual(glob["suma_retraso_significativo_minutos"], 20)
        self.assertEqual(glob["first_aggregated_date"], MONDAY.isoformat())
        self.assertEqual(glob["last_aggregated_date"], MONDAY.isoformat())

    def test_global_first_aggregated_date_does_not_move_forward_on_later_days(self):
        self._writer().update_daily_metrics([_record("04154", "Madrid", 20)], MONDAY, NOW_LOCAL)
        self._writer().update_daily_metrics([_record("04154", "Madrid", 30)], TUESDAY, NOW_LOCAL)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["first_aggregated_date"], MONDAY.isoformat())
        self.assertEqual(glob["last_aggregated_date"], TUESDAY.isoformat())
        self.assertEqual(glob["total_viajes"], 2)

    def test_global_first_aggregated_date_moves_back_when_an_earlier_day_is_backfilled(self):
        # Caso real: el pipeline en vivo crea el item GLOBAL con la fecha de
        # ayer, y luego se ejecuta scripts/backfill_metrics.py hacia atrás
        # (orden cronológico ascendente, pero empezando después de que el
        # item ya existiera). first_aggregated_date debe pasar a ser la
        # fecha más antigua vista, no quedarse congelada en la primera vez
        # que el item se creó.
        self._writer().update_daily_metrics([_record("04154", "Madrid", 20)], TUESDAY, NOW_LOCAL)
        self._writer().update_daily_metrics([_record("04154", "Madrid", 30)], MONDAY, NOW_LOCAL)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["first_aggregated_date"], MONDAY.isoformat())
        self.assertEqual(glob["last_aggregated_date"], MONDAY.isoformat())
        self.assertEqual(glob["total_viajes"], 2)

    def test_global_por_dia_semana_accumulates(self):
        self._writer().update_daily_metrics([_record("04154", "Madrid", 20)], MONDAY, NOW_LOCAL)
        self._writer().update_daily_metrics([_record("04154", "Madrid", 90)], TUESDAY, NOW_LOCAL)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["por_dia_semana"]["0"]["total_viajes"], 1)  # lunes
        self.assertEqual(glob["por_dia_semana"]["0"]["viajes_retraso_significativo"], 1)
        self.assertEqual(glob["por_dia_semana"]["1"]["total_viajes"], 1)  # martes
        self.assertEqual(glob["por_dia_semana"]["1"]["viajes_retraso_significativo"], 1)

    def test_global_por_franja_horaria_buckets_by_hour(self):
        records = [
            _record("04154", "Madrid", 20, hora_paso_zamora="07:30"),  # mañana
            _record("04475", "Galicia", 30, hora_paso_zamora="15:45"),  # tarde
            _record("04200", "Galicia", 90, hora_paso_zamora="21:10"),  # noche
        ]

        self._writer().update_daily_metrics(records, MONDAY, NOW_LOCAL)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["por_franja_horaria"]["manana"]["total_viajes"], 1)
        self.assertEqual(glob["por_franja_horaria"]["tarde"]["total_viajes"], 1)
        self.assertEqual(glob["por_franja_horaria"]["noche"]["total_viajes"], 1)
        self.assertEqual(glob["por_franja_horaria"]["noche"]["viajes_retraso_significativo"], 1)

    def test_global_franja_noche_is_catch_all_for_early_morning_hours(self):
        # Un retraso que empuja la hora de paso más allá de medianoche
        # (p. ej. 02:00) cae igualmente en "noche", no queda sin clasificar.
        records = [_record("04154", "Madrid", 20, hora_paso_zamora="02:00")]

        self._writer().update_daily_metrics(records, MONDAY, NOW_LOCAL)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["por_franja_horaria"]["noche"]["total_viajes"], 1)
        self.assertNotIn("manana", glob["por_franja_horaria"])
        self.assertNotIn("tarde", glob["por_franja_horaria"])

    def test_global_skips_records_without_hora_paso_zamora_in_franja_horaria(self):
        # Caso real (ver _process_madrid_train): un tren puede marcarse
        # entregado sin hora_paso_zamora. Debe seguir contando en los
        # contadores generales pero no en por_franja_horaria.
        records = [_record("04154", "Madrid", 20, hora_paso_zamora=None)]

        self._writer().update_daily_metrics(records, MONDAY, NOW_LOCAL)

        glob = self.get_metrics_item("GLOBAL")
        self.assertEqual(glob["total_viajes"], 1)
        _assert_buckets(self, glob, viajes_bucket_significativo=1)
        self.assertEqual(glob["por_franja_horaria"], {})


if __name__ == "__main__":
    unittest.main()
