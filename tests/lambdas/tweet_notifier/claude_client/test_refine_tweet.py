import json
import unittest
from unittest.mock import patch

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path setup
import claude_client
from tests.dummies.fake_claude import fake_refusal_response, fake_tweet_response
from tests.dummies.log_extra import SAMPLE_LOG_EXTRA

ALERT = {
    "cod_comercial": "04154",
    "sentido": "Madrid",
    "hora_programada": "08:56",
    "hora_llegada_corregida": "09:16",
    "minutos_retraso": 20,
    "fecha": "2026-08-03",
    "es_tren_madrugador": True,
}

DRAFTED = {"tweet_text": "x" * 275, "hashtags": ["#ZamoraNecesitaTren", "#Renfe"]}


class TestRefineTweet(unittest.TestCase):
    def test_asks_claude_to_shorten_tweet_text_only(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_tweet_response("texto corto", DRAFTED["hashtags"]),
        ) as mock_invoke:
            result = claude_client.refine_tweet(ALERT, DRAFTED, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {"tweet_text": "texto corto", "hashtags": DRAFTED["hashtags"]})

        body = json.loads(mock_invoke.call_args.kwargs["body"])
        self.assertIn(DRAFTED["tweet_text"], body["messages"][0]["content"])
        self.assertIn("04154", body["messages"][0]["content"])

    def test_keeps_original_hashtags_even_if_claude_returns_different_ones(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_tweet_response("texto corto", ["#Otro"]),
        ):
            result = claude_client.refine_tweet(ALERT, DRAFTED, SAMPLE_LOG_EXTRA)

        self.assertEqual(result["hashtags"], DRAFTED["hashtags"])

    def test_raises_on_non_end_turn_stop_reason(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_refusal_response(),
        ):
            with self.assertRaises(RuntimeError):
                claude_client.refine_tweet(ALERT, DRAFTED, SAMPLE_LOG_EXTRA)


if __name__ == "__main__":
    unittest.main()
