import unittest
from datetime import date

from tests.dummies import api_env


class TestParseDateParam(unittest.TestCase):
    def setUp(self):
        self.handler = api_env.import_api_handler()

    def test_parses_valid_iso_date(self):
        event = {"pathParameters": {"date": "2026-01-05"}}

        result = self.handler._parse_date_param(event)

        self.assertEqual(result, date(2026, 1, 5))

    def test_returns_none_for_malformed_date(self):
        event = {"pathParameters": {"date": "not-a-date"}}

        self.assertIsNone(self.handler._parse_date_param(event))

    def test_returns_none_for_wrong_format(self):
        event = {"pathParameters": {"date": "05/01/2026"}}

        self.assertIsNone(self.handler._parse_date_param(event))

    def test_returns_none_when_date_key_missing(self):
        event = {"pathParameters": {}}

        self.assertIsNone(self.handler._parse_date_param(event))

    def test_returns_none_when_path_parameters_missing(self):
        event = {}

        self.assertIsNone(self.handler._parse_date_param(event))


if __name__ == "__main__":
    unittest.main()
