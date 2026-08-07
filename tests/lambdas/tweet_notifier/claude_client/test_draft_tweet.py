import json
import unittest
from unittest.mock import patch

from tests.dummies import tweet_notifier_env  # noqa: F401 - sys.path setup
import claude_client
import xfetch_client
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


class TestDraftTweet(unittest.TestCase):
    def setUp(self):
        # Las tendencias son un enriquecimiento aparte (xfetch_client, no
        # Bedrock) — se mockean a "sin tendencias" salvo que el test diga
        # lo contrario, para no depender de xfetch.io/Secrets Manager aquí.
        patcher = patch.object(xfetch_client, "get_trending_hashtags", return_value=[])
        self.mock_trends = patcher.start()
        self.addCleanup(patcher.stop)

    def test_sends_expected_request_shape(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_tweet_response("texto", ["#ZamoraNecesitaTren"]),
        ) as mock_invoke:
            claude_client.draft_tweet(ALERT, SAMPLE_LOG_EXTRA)

        kwargs = mock_invoke.call_args.kwargs
        self.assertEqual(kwargs["modelId"], claude_client.CLAUDE_MODEL_ID)

        body = json.loads(kwargs["body"])
        self.assertEqual(body["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(body["system"], claude_client.SYSTEM_PROMPT)
        self.assertEqual(body["output_config"]["format"]["schema"], claude_client.OUTPUT_SCHEMA)
        self.assertIn("04154", body["messages"][0]["content"])

    def test_includes_trending_hashtags_in_prompt(self):
        self.mock_trends.return_value = ["#TendenciaReal"]
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_tweet_response("texto", ["#ZamoraNecesitaTren"]),
        ) as mock_invoke:
            claude_client.draft_tweet(ALERT, SAMPLE_LOG_EXTRA)

        body = json.loads(mock_invoke.call_args.kwargs["body"])
        self.assertIn("#TendenciaReal", body["messages"][0]["content"])

    def test_parses_tweet_text_and_hashtags(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_tweet_response(
                "El tren madrugador llega tarde otra vez",
                ["#ZamoraNecesitaTren", "#Renfe"],
            ),
        ):
            result = claude_client.draft_tweet(ALERT, SAMPLE_LOG_EXTRA)

        self.assertEqual(result, {
            "tweet_text": "El tren madrugador llega tarde otra vez",
            "hashtags": ["#ZamoraNecesitaTren", "#Renfe"],
        })

    def test_adds_advocacy_hashtag_if_missing(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_tweet_response("texto", ["#Renfe", "#Zamora"]),
        ):
            result = claude_client.draft_tweet(ALERT, SAMPLE_LOG_EXTRA)

        self.assertEqual(result["hashtags"], ["#Renfe", "#Zamora", "#TrenMadrugadorYa"])

    def test_keeps_existing_advocacy_hashtag_untouched(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_tweet_response("texto", ["#TrenMadrugadorYa", "#Renfe"]),
        ):
            result = claude_client.draft_tweet(ALERT, SAMPLE_LOG_EXTRA)

        self.assertEqual(result["hashtags"], ["#TrenMadrugadorYa", "#Renfe"])

    def test_raises_on_non_end_turn_stop_reason(self):
        with patch.object(
            claude_client.bedrock_runtime, "invoke_model",
            return_value=fake_refusal_response(),
        ):
            with self.assertRaises(RuntimeError):
                claude_client.draft_tweet(ALERT, SAMPLE_LOG_EXTRA)


if __name__ == "__main__":
    unittest.main()
