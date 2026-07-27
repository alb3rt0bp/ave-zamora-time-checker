import unittest
from unittest.mock import patch

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from renfe_client import RenfeClient


class TestGetTrenesConEstaciones(unittest.TestCase):
    def setUp(self):
        self.client = RenfeClient(SAMPLE_LOG_EXTRA)

    @patch("urllib.request.urlopen")
    def test_returns_bare_list(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json([{"codComercial": "M100"}])

        result = self.client.get_trenes_con_estaciones()

        self.assertEqual(result, [{"codComercial": "M100"}])

    @patch("urllib.request.urlopen")
    def test_returns_trenes_key_from_dict(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"trenes": [{"codComercial": "M100"}]})

        result = self.client.get_trenes_con_estaciones()

        self.assertEqual(result, [{"codComercial": "M100"}])

    @patch("urllib.request.urlopen")
    def test_returns_data_key_from_dict(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"data": [{"codComercial": "G100"}]})

        result = self.client.get_trenes_con_estaciones()

        self.assertEqual(result, [{"codComercial": "G100"}])

    @patch("urllib.request.urlopen")
    def test_returns_empty_list_for_unexpected_shape(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json(42)

        result = self.client.get_trenes_con_estaciones()

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
