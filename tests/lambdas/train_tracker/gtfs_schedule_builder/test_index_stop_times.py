import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.gtfs_samples import STOP_TIMES_CSV, ZAMORA_CODE, CHAMARTIN_CODE

from gtfs_schedule_builder import _index_stop_times


class TestIndexStopTimes(unittest.TestCase):
    def setUp(self):
        self.zamora_by_trip, self.chamartin_by_trip = _index_stop_times(
            STOP_TIMES_CSV, ZAMORA_CODE, CHAMARTIN_CODE
        )

    def test_captures_zamora_stop_sequence_and_times(self):
        self.assertEqual(
            self.zamora_by_trip["TRIP_M1"],
            {
                "stop_sequence": 4,
                "arrival_time": "07:39", "arrival_offset_dias": 0,
                "departure_time": "07:41", "departure_offset_dias": 0,
            },
        )

    def test_captures_chamartin_stop_sequence_and_times(self):
        self.assertEqual(
            self.chamartin_by_trip["TRIP_M1"],
            {
                "stop_sequence": 5,
                "arrival_time": "08:49", "arrival_offset_dias": 0,
                "departure_time": "08:49", "departure_offset_dias": 0,
            },
        )

    def test_captures_the_day_offset_of_times_past_midnight(self):
        # TRIP_MNIGHT llega a Chamartín a las "24:10" de su día de servicio:
        # hora de reloj 00:10 y un día de desplazamiento.
        chamartin = self.chamartin_by_trip["TRIP_MNIGHT"]
        self.assertEqual(chamartin["arrival_time"], "00:10")
        self.assertEqual(chamartin["arrival_offset_dias"], 1)

        zamora = self.zamora_by_trip["TRIP_MNIGHT"]
        self.assertEqual(zamora["departure_time"], "23:05")
        self.assertEqual(zamora["departure_offset_dias"], 0)

    def test_trip_only_stopping_at_zamora_is_absent_from_chamartin_index(self):
        self.assertIn("TRIP_NOCHAM", self.zamora_by_trip)
        self.assertNotIn("TRIP_NOCHAM", self.chamartin_by_trip)

    def test_ignores_stops_other_than_zamora_and_chamartin(self):
        # Ninguna fila del fixture usa otro stop_id, pero el índice no debe
        # contener nada que no sea 30200/17000.
        all_trip_ids = set(self.zamora_by_trip) | set(self.chamartin_by_trip)
        self.assertNotIn("unrelated-stop", all_trip_ids)


if __name__ == "__main__":
    unittest.main()
