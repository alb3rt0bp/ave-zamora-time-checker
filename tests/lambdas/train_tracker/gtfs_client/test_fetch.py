import unittest
from unittest.mock import patch
import urllib.error

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.fake_http import FakeHTTPResponse, raise_http_error, raise_url_error
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from gtfs_client import GtfsClient, GTFS_ZIP_URL


class TestFetch(unittest.TestCase):
    def setUp(self):
        self.client = GtfsClient(SAMPLE_LOG_EXTRA)

    @patch("urllib.request.urlopen")
    def test_returns_raw_bytes_on_success(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(b"PK\x03\x04fake-zip-bytes")

        result = self.client._fetch(GTFS_ZIP_URL)

        self.assertEqual(result, b"PK\x03\x04fake-zip-bytes")

    @patch("urllib.request.urlopen", side_effect=raise_http_error)
    def test_reraises_http_error(self, mock_urlopen):
        with self.assertRaises(urllib.error.HTTPError):
            self.client._fetch(GTFS_ZIP_URL)

    @patch("urllib.request.urlopen", side_effect=raise_url_error)
    def test_reraises_url_error(self, mock_urlopen):
        with self.assertRaises(urllib.error.URLError):
            self.client._fetch(GTFS_ZIP_URL)

    @patch("urllib.request.urlopen")
    def test_uses_configured_timeout(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(b"")
        client = GtfsClient(SAMPLE_LOG_EXTRA, timeout_seconds=7)

        client._fetch(GTFS_ZIP_URL)

        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 7)


if __name__ == "__main__":
    unittest.main()
