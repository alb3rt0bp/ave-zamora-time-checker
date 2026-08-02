import unittest
from unittest.mock import patch

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.fake_http import fake_urlopen_json
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.gtfsrt_samples import ENTITY_M100

from gtfsrt_client import GtfsRtClient


class TestGetTripUpdates(unittest.TestCase):
    def setUp(self):
        self.client = GtfsRtClient(SAMPLE_LOG_EXTRA)

    @patch("urllib.request.urlopen")
    def test_returns_entity_list(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"header": {}, "entity": [ENTITY_M100]})

        result = self.client.get_trip_updates()

        self.assertEqual(result, [ENTITY_M100])

    @patch("urllib.request.urlopen")
    def test_returns_empty_list_when_entity_key_missing(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"header": {}})

        result = self.client.get_trip_updates()

        self.assertEqual(result, [])

    @patch("urllib.request.urlopen")
    def test_returns_empty_list_for_unexpected_shape(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json(["not", "a", "dict"])

        result = self.client.get_trip_updates()

        self.assertEqual(result, [])

    @patch("urllib.request.urlopen")
    def test_calls_trip_updates_url(self, mock_urlopen):
        mock_urlopen.return_value = fake_urlopen_json({"entity": []})

        self.client.get_trip_updates()

        called_request = mock_urlopen.call_args[0][0]
        self.assertIn("trip_updates_LD.json", called_request.full_url)


if __name__ == "__main__":
    unittest.main()
