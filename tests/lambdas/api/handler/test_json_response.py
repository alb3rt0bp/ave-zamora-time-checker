import json
import unittest

from tests.dummies import api_env


class TestJsonResponse(unittest.TestCase):
    def setUp(self):
        self.handler = api_env.import_api_handler()

    def test_sets_status_code(self):
        response = self.handler._json_response(200, {"foo": "bar"})

        self.assertEqual(response["statusCode"], 200)

    def test_serializes_payload_as_json_body(self):
        response = self.handler._json_response(200, {"foo": "bar"})

        self.assertEqual(json.loads(response["body"]), {"foo": "bar"})

    def test_sets_content_type_header(self):
        response = self.handler._json_response(200, {})

        self.assertEqual(response["headers"]["Content-Type"], "application/json")

    def test_sets_cors_allow_origin_header(self):
        response = self.handler._json_response(200, {})

        self.assertEqual(response["headers"]["Access-Control-Allow-Origin"], "*")

    def test_supports_error_status_codes(self):
        response = self.handler._json_response(404, {"error": "no dumped yet"})

        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(json.loads(response["body"]), {"error": "no dumped yet"})

    def test_supports_list_payloads(self):
        response = self.handler._json_response(200, [{"cod_comercial": "04154"}])

        self.assertEqual(json.loads(response["body"]), [{"cod_comercial": "04154"}])


if __name__ == "__main__":
    unittest.main()
