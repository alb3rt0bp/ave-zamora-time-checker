import base64
import hashlib
import hmac
import unittest
import urllib.parse

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path setup
from x_client import XClient

CREDENTIALS = {
    "consumer_key": "ck",
    "consumer_secret": "cs",
    "access_token": "at",
    "access_token_secret": "ats",
}


class TestOAuth1Header(unittest.TestCase):
    def setUp(self):
        self.client = XClient(CREDENTIALS, {"span_id": "test"})

    def test_header_includes_required_oauth_params(self):
        header = self.client._oauth1_header(
            "POST", "https://api.x.com/2/tweets", nonce="fixednonce", timestamp="1700000000"
        )

        self.assertTrue(header.startswith("OAuth "))
        self.assertIn('oauth_consumer_key="ck"', header)
        self.assertIn('oauth_token="at"', header)
        self.assertIn('oauth_signature_method="HMAC-SHA1"', header)
        self.assertIn('oauth_version="1.0"', header)
        self.assertIn('oauth_nonce="fixednonce"', header)
        self.assertIn('oauth_timestamp="1700000000"', header)

    def test_uses_random_nonce_and_timestamp_when_not_given(self):
        header_a = self.client._oauth1_header("POST", "https://api.x.com/2/tweets")
        header_b = self.client._oauth1_header("POST", "https://api.x.com/2/tweets")

        self.assertNotEqual(header_a, header_b)

    def test_signature_matches_independently_computed_value(self):
        # Recalcula la firma con su propia implementación (sin llamar al
        # código de producción) para detectar errores de orden/encoding.
        nonce, timestamp = "fixednonce", "1700000000"
        method, url = "POST", "https://api.x.com/2/tweets"

        header = self.client._oauth1_header(method, url, nonce=nonce, timestamp=timestamp)

        oauth_params = {
            "oauth_consumer_key": "ck",
            "oauth_nonce": nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": timestamp,
            "oauth_token": "at",
            "oauth_version": "1.0",
        }
        param_string = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted(oauth_params.items())
        )
        base_string = "&".join([
            method,
            urllib.parse.quote(url, safe=""),
            urllib.parse.quote(param_string, safe=""),
        ])
        signing_key = "&".join([
            urllib.parse.quote("cs", safe=""),
            urllib.parse.quote("ats", safe=""),
        ])
        expected_signature = base64.b64encode(
            hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1).digest()
        ).decode("utf-8")

        expected_fragment = f'oauth_signature="{urllib.parse.quote(expected_signature, safe="")}"'
        self.assertIn(expected_fragment, header)


if __name__ == "__main__":
    unittest.main()
