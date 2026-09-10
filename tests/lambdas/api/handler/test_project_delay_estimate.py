import unittest

from tests.dummies.api_handler_test_case import ApiHandlerTestCase


class TestProjectDelayEstimate(ApiHandlerTestCase):
    def test_returns_none_without_observations(self):
        self.assertIsNone(self.handler._project_delay_estimate({}, base="tren"))

    def test_projects_median_and_range_from_the_histogram(self):
        # Muestra equivalente: [0, 0, 2, 2, 6, 6, 6, 12, 20, 45] (10 viajes).
        histogram = {"0": 2, "2": 2, "6": 3, "12": 1, "20": 1, "45": 1}

        estimate = self.handler._project_delay_estimate(histogram, base="tren")

        self.assertEqual(estimate["mediana_minutos"], 6)
        self.assertEqual(estimate["p25_minutos"], 2)
        self.assertEqual(estimate["p75_minutos"], 12)
        self.assertEqual(estimate["p90_minutos"], 20)   # índice round(0.9*9)=8; el 45 es el máximo, no el P90
        self.assertEqual(estimate["viajes_estimacion"], 10)
        self.assertEqual(estimate["base"], "tren")

    def test_base_is_carried_through_verbatim(self):
        estimate = self.handler._project_delay_estimate({"3": 4}, base="sentido")

        self.assertEqual(estimate["base"], "sentido")

    def test_percentiles_are_monotonically_ordered(self):
        histogram = {"-4": 1, "0": 5, "3": 9, "11": 4, "60": 2, "149": 1}

        estimate = self.handler._project_delay_estimate(histogram, base="tren")

        self.assertLessEqual(estimate["p25_minutos"], estimate["mediana_minutos"])
        self.assertLessEqual(estimate["mediana_minutos"], estimate["p75_minutos"])
        self.assertLessEqual(estimate["p75_minutos"], estimate["p90_minutos"])

    def test_punctual_train_yields_a_zero_or_negative_median(self):
        # El 04114 real: mediana 0, P25 negativo. No debe "corregirse" a un
        # mínimo de 0 minutos — llegar antes de hora es un dato válido.
        histogram = {"-2": 12, "0": 10, "3": 10, "7": 5, "39": 1}

        estimate = self.handler._project_delay_estimate(histogram, base="tren")

        self.assertEqual(estimate["p25_minutos"], -2)
        self.assertEqual(estimate["mediana_minutos"], 0)


if __name__ == "__main__":
    unittest.main()
