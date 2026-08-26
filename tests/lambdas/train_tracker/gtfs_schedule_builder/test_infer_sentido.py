import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from gtfs_schedule_builder import _infer_sentido


class TestInferSentido(unittest.TestCase):
    def test_chamartin_after_zamora_is_madrid(self):
        zamora = {"stop_sequence": 4}
        chamartin = {"stop_sequence": 5}

        self.assertEqual(_infer_sentido(zamora, chamartin, "T1", SAMPLE_LOG_EXTRA), "Madrid")

    def test_chamartin_before_zamora_is_galicia(self):
        zamora = {"stop_sequence": 2}
        chamartin = {"stop_sequence": 1}

        self.assertEqual(_infer_sentido(zamora, chamartin, "T1", SAMPLE_LOG_EXTRA), "Galicia")

    def test_equal_sequence_returns_none(self):
        zamora = {"stop_sequence": 3}
        chamartin = {"stop_sequence": 3}

        self.assertIsNone(_infer_sentido(zamora, chamartin, "T1", SAMPLE_LOG_EXTRA))

    def test_equal_sequence_logs_warning_with_trip_id(self):
        zamora = {"stop_sequence": 3}
        chamartin = {"stop_sequence": 3}

        with self.assertLogs("train_tracker.gtfs_schedule_builder", level="WARNING") as logs:
            _infer_sentido(zamora, chamartin, "TRIP_WEIRD", SAMPLE_LOG_EXTRA)

        self.assertIn("TRIP_WEIRD", logs.output[0])


if __name__ == "__main__":
    unittest.main()
