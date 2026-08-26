import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.gtfs_samples import TRIPS_CSV

from gtfs_schedule_builder import _index_trips


class TestIndexTrips(unittest.TestCase):
    def test_captures_cod_comercial_and_service_id_for_candidates(self):
        result = _index_trips(TRIPS_CSV, {"TRIP_M1"}, SAMPLE_LOG_EXTRA)

        self.assertEqual(
            result["TRIP_M1"], {"cod_comercial": "04154", "service_id": "SVC_LABORABLE"}
        )

    def test_ignores_trip_ids_not_in_candidates(self):
        result = _index_trips(TRIPS_CSV, {"TRIP_M1"}, SAMPLE_LOG_EXTRA)

        self.assertNotIn("TRIP_G1", result)

    def test_skips_candidate_without_trip_short_name(self):
        result = _index_trips(TRIPS_CSV, {"TRIP_NOSHORTNAME"}, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {})

    def test_skips_candidate_without_trip_short_name_logs_warning(self):
        with self.assertLogs("train_tracker.gtfs_schedule_builder", level="WARNING") as logs:
            _index_trips(TRIPS_CSV, {"TRIP_NOSHORTNAME"}, SAMPLE_LOG_EXTRA)

        self.assertIn("TRIP_NOSHORTNAME", logs.output[0])

    def test_empty_candidate_set_returns_empty_dict(self):
        result = _index_trips(TRIPS_CSV, set(), SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
