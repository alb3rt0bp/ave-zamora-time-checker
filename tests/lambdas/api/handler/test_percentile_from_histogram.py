import unittest

from tests.dummies.api_handler_test_case import ApiHandlerTestCase


class TestPercentileFromHistogram(ApiHandlerTestCase):
    def test_returns_none_for_empty_histogram(self):
        self.assertIsNone(self.handler._percentile_from_histogram({}, 0.5))

    def test_single_observation_is_every_percentile(self):
        histogram = {"7": 1}

        for q in (0.0, 0.25, 0.5, 0.9, 1.0):
            self.assertEqual(self.handler._percentile_from_histogram(histogram, q), 7, q)

    def test_matches_the_sorted_sample_by_nearest_rank(self):
        # Muestra equivalente: [0, 0, 1, 5, 5, 5, 10, 30] (8 viajes).
        histogram = {"0": 2, "1": 1, "5": 3, "10": 1, "30": 1}

        # Índice = round(q * (n-1)) sobre la muestra ordenada.
        self.assertEqual(self.handler._percentile_from_histogram(histogram, 0.25), 1)   # índice 2
        self.assertEqual(self.handler._percentile_from_histogram(histogram, 0.50), 5)   # índice 4 (redondea a 4)
        self.assertEqual(self.handler._percentile_from_histogram(histogram, 0.75), 5)   # índice 5
        self.assertEqual(self.handler._percentile_from_histogram(histogram, 0.90), 10)  # índice round(0.9*7)=6

    def test_negative_delays_order_before_zero(self):
        # Un tren adelantado es un dato real, no un cero: debe poder salir
        # como percentil bajo en vez de quedar truncado.
        histogram = {"-3": 3, "0": 1, "4": 1}

        self.assertEqual(self.handler._percentile_from_histogram(histogram, 0.0), -3)
        self.assertEqual(self.handler._percentile_from_histogram(histogram, 0.25), -3)
        self.assertEqual(self.handler._percentile_from_histogram(histogram, 1.0), 4)

    def test_always_returns_an_observed_value_never_an_interpolation(self):
        # Con n par la mediana "clásica" interpolaría a 7.5; la pantalla
        # anuncia una hora concreta, así que se devuelve un minuto real.
        histogram = {"5": 1, "10": 1}

        median = self.handler._percentile_from_histogram(histogram, 0.5)

        self.assertIn(median, (5, 10))
        self.assertIsInstance(median, int)

    def test_reads_decimal_counts_from_dynamodb(self):
        # DynamoDB devuelve los números como Decimal; sin castear, sorted()
        # y la suma seguirían funcionando pero el conteo compararía Decimal
        # con int en el índice objetivo.
        from decimal import Decimal
        histogram = {"2": Decimal("3"), "9": Decimal("1")}

        self.assertEqual(self.handler._percentile_from_histogram(histogram, 0.5), 2)
        self.assertEqual(self.handler._percentile_from_histogram(histogram, 1.0), 9)


if __name__ == "__main__":
    unittest.main()
