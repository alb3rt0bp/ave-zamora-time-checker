import unittest
from unittest.mock import patch

import boto3
from moto import mock_aws

from tests.dummies import trend_fetcher_env
from tests.dummies.fake_http import FakeHTTPResponse, fake_urlopen_json, raise_url_error
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA
from tests.dummies.xfetch_samples import TRENDS_SPAIN_REAL_SAMPLE
import xfetch_client


class TestGetTrendingHashtags(unittest.TestCase):
    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        secretsmanager = boto3.client("secretsmanager", region_name=trend_fetcher_env.AWS_REGION)
        secretsmanager.create_secret(
            Name=trend_fetcher_env.XFETCH_API_KEY_SECRET_ARN,
            SecretString="test-xfetch-key",
        )
        xfetch_client._api_key_cache = None  # aislar la caché entre tests

    def test_returns_only_hashtag_trends(self):
        payload = {
            "data": [
                {"trend_name": "#TrenMadrugador"},
                {"trend_name": "Algo sin hashtag"},
                {"trend_name": "#Renfe"},
            ],
            "meta": {"request_id": "r1", "credits": {"charged": 4, "remaining": 996}},
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json(payload)
            result = xfetch_client.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, ["#TrenMadrugador", "#Renfe"])

    def test_returns_only_hashtag_trends_from_real_sample(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json(TRENDS_SPAIN_REAL_SAMPLE)
            result = xfetch_client.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, ["#ArianaxFNAC", "#7AgostoESP", "#This_And_That", "#LaHora7A"])

    def test_sends_spain_woeid_and_bearer_token(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = fake_urlopen_json(TRENDS_SPAIN_REAL_SAMPLE)
            xfetch_client.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        sent_request = mock_urlopen.call_args[0][0]
        self.assertIn("woeid=23424950", sent_request.full_url)
        self.assertEqual(sent_request.get_header("Authorization"), "Bearer test-xfetch-key")

    def test_returns_empty_list_on_network_error(self):
        with patch("urllib.request.urlopen", side_effect=raise_url_error):
            result = xfetch_client.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [])

    def test_returns_empty_list_on_malformed_json(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = FakeHTTPResponse(b"not json")
            result = xfetch_client.get_trending_hashtags(SAMPLE_LOG_EXTRA)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
