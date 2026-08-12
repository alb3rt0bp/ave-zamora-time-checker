import json
import unittest
from unittest.mock import patch

from tests.dummies.api_handler_test_case import ApiHandlerTestCase
from tests.dummies.fake_http import fake_urlopen_json, raise_http_error, raise_url_error

SAMPLE_FLOTA = {
    "fechaActualizacion": "2026-08-08T09:46:58",
    "trenes": [
        {
            "codComercial": "04154",
            "codEstAnt": "30200",
            "ultRetraso": "6",
            "latitud": 41.5034,
            "longitud": -5.7447,
        },
    ],
}


class FakeContext:
    aws_request_id = "get-flota-test"


class TestGetFlotaHandler(ApiHandlerTestCase):
    def test_proxies_flota_json_with_cors_header(self):
        with patch("api_handler.urllib.request.urlopen", return_value=fake_urlopen_json(SAMPLE_FLOTA)):
            response = self.handler.get_flota_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Access-Control-Allow-Origin"], "*")
        body = json.loads(response["body"])
        self.assertEqual(body, SAMPLE_FLOTA)

    def test_returns_502_on_upstream_http_error(self):
        with patch("api_handler.urllib.request.urlopen", side_effect=raise_http_error):
            response = self.handler.get_flota_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 502)

    def test_returns_502_on_upstream_network_error(self):
        with patch("api_handler.urllib.request.urlopen", side_effect=raise_url_error):
            response = self.handler.get_flota_handler({}, FakeContext())

        self.assertEqual(response["statusCode"], 502)


if __name__ == "__main__":
    unittest.main()
