import unittest

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup

from schedule_resolver import _with_day_offsets


class TestWithDayOffsets(unittest.TestCase):
    def test_keeps_the_offsets_resolved_from_gtfs(self):
        train = {
            "cod_comercial": "04777", "sentido": "Madrid",
            "hora_salida": "23:05", "hora_llegada_destino": "00:10",
            "offset_dias_salida": 0, "offset_dias_llegada": 1,
        }

        self.assertEqual(_with_day_offsets(train), train)

    def test_infers_the_arrival_offset_when_it_is_earlier_than_the_departure(self):
        # Fichero estático de reserva (o caché antigua): solo horas de reloj.
        # Una llegada anterior a la salida solo puede significar que el tren
        # ha cruzado la medianoche.
        train = {
            "cod_comercial": "M900", "sentido": "Madrid",
            "hora_salida": "23:05", "hora_llegada_destino": "00:10",
        }

        result = _with_day_offsets(train)

        self.assertEqual(result["offset_dias_llegada"], 1)
        self.assertEqual(result["offset_dias_salida"], 0)

    def test_a_normal_train_gets_zero_offsets(self):
        train = {
            "cod_comercial": "M100", "sentido": "Madrid",
            "hora_salida": "07:00", "hora_llegada_destino": "08:30",
        }

        result = _with_day_offsets(train)

        self.assertEqual(result["offset_dias_salida"], 0)
        self.assertEqual(result["offset_dias_llegada"], 0)

    def test_does_not_mutate_the_original_train(self):
        train = {"cod_comercial": "M100", "hora_salida": "07:00", "hora_llegada_destino": "08:30"}

        _with_day_offsets(train)

        self.assertNotIn("offset_dias_llegada", train)

    def test_a_train_without_times_does_not_blow_up(self):
        result = _with_day_offsets({"cod_comercial": "M100"})

        self.assertEqual(result["offset_dias_llegada"], 0)


if __name__ == "__main__":
    unittest.main()
