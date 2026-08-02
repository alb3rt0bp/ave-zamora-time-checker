import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.gtfsrt_samples import (
    ENTITY_M100,
    ENTITY_G100,
    ENTITY_UNRELATED,
    ENTITY_M100_COLLISION_A,
    ENTITY_M100_COLLISION_B,
    ENTITY_M100_NO_ZAMORA_STOP,
    ENTITY_MISSING_TRIP_UPDATE,
    ENTITY_MISSING_TRIP,
    ENTITY_MISSING_TRIP_ID,
    ENTITY_MISSING_STOP_TIME_UPDATE,
    ENTITY_MISSING_ARRIVAL,
    ENTITY_NON_NUMERIC_DELAY,
    ENTITY_NON_NUMERIC_EPOCH,
)

from gtfsrt_matcher import find_stop_time_update

ZAMORA_CODE = "30200"
CHAMARTIN_CODE = "17000"


class TestFindStopTimeUpdate(unittest.TestCase):
    def test_match_found_returns_minutos_retraso_and_hora_llegada(self):
        result = find_stop_time_update([ENTITY_M100], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {"minutos_retraso": 3, "hora_llegada": "08:34"})

    def test_converts_seconds_to_minutes_not_a_raw_copy(self):
        # Regresión explícita del bug de unidades: GTFS-RT da el delay en
        # SEGUNDOS (300s para Chamartín en el fixture), no en minutos.
        result = find_stop_time_update([ENTITY_M100], "M100", CHAMARTIN_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result["minutos_retraso"], 5)

    def test_hora_llegada_is_europe_madrid_not_utc(self):
        # El epoch de ZAMORA_EPOCH corresponde a las 08:34 en Europe/Madrid
        # pero a las 07:34 en UTC — si el código convirtiera a UTC por error,
        # esta aserción fallaría visiblemente en vez de colar por casualidad.
        result = find_stop_time_update([ENTITY_M100], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result["hora_llegada"], "08:34")

    def test_galicia_train_zero_delay(self):
        result = find_stop_time_update([ENTITY_G100], "G100", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {"minutos_retraso": 0, "hora_llegada": "08:34"})

    def test_empty_cod_comercial_returns_none_immediately(self):
        result = find_stop_time_update([ENTITY_M100], "", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)

    def test_no_matching_trip_id_returns_none(self):
        result = find_stop_time_update([ENTITY_UNRELATED], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)

    def test_empty_entities_list_returns_none(self):
        result = find_stop_time_update([], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)

    def test_matching_trip_without_requested_stop_returns_none(self):
        result = find_stop_time_update(
            [ENTITY_M100_NO_ZAMORA_STOP], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA
        )

        self.assertIsNone(result)

    def test_ambiguous_match_returns_none_instead_of_guessing(self):
        result = find_stop_time_update(
            [ENTITY_M100_COLLISION_A, ENTITY_M100_COLLISION_B], "M100", CHAMARTIN_CODE, SAMPLE_LOG_EXTRA
        )

        self.assertIsNone(result)

    def test_ambiguous_match_logs_warning_with_candidate_trip_ids(self):
        with self.assertLogs("gtfsrt_matcher", level="WARNING") as logs:
            find_stop_time_update(
                [ENTITY_M100_COLLISION_A, ENTITY_M100_COLLISION_B], "M100", CHAMARTIN_CODE, SAMPLE_LOG_EXTRA
            )

        self.assertIn("M10012026-01-05", logs.output[0])
        self.assertIn("M10022026-01-05", logs.output[0])

    def test_missing_nested_keys_never_raise_and_return_none(self):
        result = find_stop_time_update(
            [ENTITY_MISSING_TRIP_UPDATE, ENTITY_MISSING_TRIP, ENTITY_MISSING_TRIP_ID],
            "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA,
        )

        self.assertIsNone(result)

    def test_missing_stop_time_update_returns_none(self):
        result = find_stop_time_update(
            [ENTITY_MISSING_STOP_TIME_UPDATE], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA
        )

        self.assertIsNone(result)

    def test_missing_arrival_returns_none(self):
        result = find_stop_time_update([ENTITY_MISSING_ARRIVAL], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA)

        self.assertIsNone(result)

    def test_non_numeric_delay_omits_minutos_retraso_but_keeps_hora_llegada(self):
        result = find_stop_time_update(
            [ENTITY_NON_NUMERIC_DELAY], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA
        )

        self.assertNotIn("minutos_retraso", result)
        self.assertEqual(result["hora_llegada"], "08:34")

    def test_non_numeric_epoch_omits_hora_llegada_but_keeps_minutos_retraso(self):
        result = find_stop_time_update(
            [ENTITY_NON_NUMERIC_EPOCH], "M100", ZAMORA_CODE, SAMPLE_LOG_EXTRA
        )

        self.assertNotIn("hora_llegada", result)
        self.assertEqual(result["minutos_retraso"], 0)


if __name__ == "__main__":
    unittest.main()
