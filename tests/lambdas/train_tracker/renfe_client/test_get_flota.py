import unittest
from unittest.mock import patch

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.renfe_samples import TRAIN_M100_EN_RUTA

from renfe_client import RenfeClient


class TestGetFlota(unittest.TestCase):
    def setUp(self):
        self.client = RenfeClient(SAMPLE_LOG_EXTRA)

    @patch("urllib.request.urlopen")
    def test_returns_list_when_api_returns_bare_list(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json([TRAIN_M100_EN_RUTA])

        result = self.client.get_flota()

        self.assertEqual(result, [TRAIN_M100_EN_RUTA])

    @patch("urllib.request.urlopen")
    def test_returns_list_when_api_wraps_in_trenes_key(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"trenes": [TRAIN_M100_EN_RUTA]})

        result = self.client.get_flota()

        self.assertEqual(result, [TRAIN_M100_EN_RUTA])

    @patch("urllib.request.urlopen")
    def test_returns_empty_list_for_unexpected_shape(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json("not-a-list-or-dict")

        result = self.client.get_flota()

        self.assertEqual(result, [])

    @patch("urllib.request.urlopen")
    def test_calls_flota_url(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json([])

        self.client.get_flota()

        called_request = mock_urlopen.call_args[0][0]
        self.assertIn("flotaLD.json", called_request.full_url)


if __name__ == "__main__":
    unittest.main()
