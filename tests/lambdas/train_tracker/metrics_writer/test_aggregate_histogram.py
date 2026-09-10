import unittest

from tests.dummies.handler_test_case import HandlerTestCase

import metrics_writer  # noqa: E402 - requiere el sys.path que fija tests.dummies.handler_test_case


def _record(minutos_retraso: int) -> dict:
    return {"cod_comercial": "04154", "sentido": "Madrid", "minutos_retraso": minutos_retraso}


class TestAggregateHistogram(HandlerTestCase):
    def test_empty_batch_yields_empty_histogram(self):
        self.assertEqual(metrics_writer.MetricsWriter._aggregate_histogram([]), {})

    def test_counts_repeated_minutes(self):
        records = [_record(6), _record(6), _record(0), _record(21)]

        histogram = metrics_writer.MetricsWriter._aggregate_histogram(records)

        self.assertEqual(histogram, {"6": 2, "0": 1, "21": 1})

    def test_keys_are_strings_because_dynamodb_maps_require_them(self):
        histogram = metrics_writer.MetricsWriter._aggregate_histogram([_record(9)])

        self.assertEqual(list(histogram), ["9"])

    def test_negative_delays_are_kept_verbatim(self):
        # Un tren adelantado no es un cero: truncarlo sesgaría al alza los
        # percentiles bajos que la pantalla de detalle publica como rango.
        histogram = metrics_writer.MetricsWriter._aggregate_histogram([_record(-3), _record(-3), _record(0)])

        self.assertEqual(histogram, {"-3": 2, "0": 1})


if __name__ == "__main__":
    unittest.main()
