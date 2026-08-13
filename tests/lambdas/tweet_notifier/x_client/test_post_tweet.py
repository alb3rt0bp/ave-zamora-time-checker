import json
import unittest
from unittest.mock import patch

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path setup
from tests.dummies.fake_http import fake_urlopen_json, raise_http_error, raise_url_error
from x_client import XClient

CREDENTIALS = {
    "consumer_key": "ck",
    "consumer_secret": "cs",
    "access_token": "at",
    "access_token_secret": "ats",
}


class TestPostTweet(unittest.TestCase):
    def setUp(self):
        self.client = XClient(CREDENTIALS, {"span_id": "test"})

    def test_sends_json_body_with_text(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "1"}})
            self.client.post_tweet("hola mundo")

        sent_request = mock_urlopen.call_args[0][0]
        self.assertEqual(sent_request.full_url, "https://api.x.com/2/tweets")
        self.assertEqual(json.loads(sent_request.data.decode("utf-8")), {"text": "hola mundo"})
        self.assertTrue(sent_request.get_header("Authorization").startswith("OAuth "))
        self.assertEqual(sent_request.get_header("Content-type"), "application/json")

    def test_returns_parsed_response(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json({"data": {"id": "123"}})
            result = self.client.post_tweet("hola")

        self.assertEqual(result, {"data": {"id": "123"}})

    def test_reraises_http_error(self):
        with patch("urllib.request.urlopen", side_effect=raise_http_error):
            with self.assertRaises(Exception):
                self.client.post_tweet("hola")

    def test_reraises_url_error(self):
        with patch("urllib.request.urlopen", side_effect=raise_url_error):
            with self.assertRaises(Exception):
                self.client.post_tweet("hola")


if __name__ == "__main__":
    unittest.main()
