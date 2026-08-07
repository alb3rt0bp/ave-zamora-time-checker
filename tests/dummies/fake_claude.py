"""
fake_claude.py
Doble de prueba para bedrock_runtime.invoke_model en claude_client.py:
construye el dict de respuesta de boto3 ({"body": <objeto con .read()>}) con
el JSON crudo de Claude dentro. Necesario porque el mock de bedrock-runtime
de moto ignora el payload y siempre devuelve {} — no permite controlar la
respuesta (ver tests/lambdas/tweet_notifier/claude_client/test_draft_tweet.py).
"""
import io
import json


def _fake_invoke_model_response(content: list, stop_reason: str = "end_turn") -> dict:
    body = json.dumps({"content": content, "stop_reason": stop_reason}).encode("utf-8")
    return {"body": io.BytesIO(body)}


def fake_tweet_response(tweet_text: str, hashtags: list, stop_reason: str = "end_turn") -> dict:
    """Respuesta de invoke_model cuyo último bloque de texto es el JSON {tweet_text, hashtags}."""
    payload = json.dumps({"tweet_text": tweet_text, "hashtags": hashtags})
    return _fake_invoke_model_response([{"type": "text", "text": payload}], stop_reason=stop_reason)


def fake_refusal_response(stop_reason: str = "refusal") -> dict:
    """Respuesta de invoke_model sin bloques de texto, simulando una negativa de Claude."""
    return _fake_invoke_model_response([], stop_reason=stop_reason)
