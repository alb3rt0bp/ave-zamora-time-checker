import io
import unittest
import zipfile
from unittest.mock import patch

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies.fake_http import FakeHTTPResponse
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

from gtfs_client import GtfsClient, REQUIRED_FILES


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _full_gtfs_zip(**overrides) -> bytes:
    files = {name: f"header\nrow-for-{name}\n" for name in REQUIRED_FILES}
    files.update(overrides)
    return _zip_bytes(files)


class TestDownloadAndExtract(unittest.TestCase):
    def setUp(self):
        self.client = GtfsClient(SAMPLE_LOG_EXTRA)

    @patch("urllib.request.urlopen")
    def test_returns_text_content_for_each_required_file(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(_full_gtfs_zip())

        result = self.client.download_and_extract()

        self.assertEqual(set(result.keys()), set(REQUIRED_FILES))
        self.assertIn("row-for-trips.txt", result["trips.txt"])

    @patch("urllib.request.urlopen")
    def test_raises_when_a_required_file_is_missing(self, mock_urlopen):
        files = {name: "x" for name in REQUIRED_FILES if name != "calendar_dates.txt"}
        mock_urlopen.return_value = FakeHTTPResponse(_zip_bytes(files))

        with self.assertRaises(FileNotFoundError) as ctx:
            self.client.download_and_extract()

        self.assertIn("calendar_dates.txt", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_decodes_utf8_bom_without_leaving_it_in_the_content(self, mock_urlopen):
        # Escribe el fichero con BOM real (bytes), no el texto decodificado a ciegas.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name in REQUIRED_FILES:
                zf.writestr(name, "header\n".encode("utf-8-sig"))
        mock_urlopen.return_value = FakeHTTPResponse(buf.getvalue())

        result = self.client.download_and_extract()

        self.assertFalse(result["trips.txt"].startswith("﻿"))
        self.assertTrue(result["trips.txt"].startswith("header"))

    @patch("urllib.request.urlopen")
    def test_ignores_extra_files_not_in_required_files(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(
            _full_gtfs_zip(**{"stops.txt": "irrelevant", "agency.txt": "irrelevant"})
        )

        result = self.client.download_and_extract()

        self.assertEqual(set(result.keys()), set(REQUIRED_FILES))


if __name__ == "__main__":
    unittest.main()
