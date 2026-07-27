"""
fake_http.py
Doble de prueba para urllib.request.urlopen: RenfeClient._fetch hace
`with urllib.request.urlopen(req, timeout=...) as response: return response.read()`,
así que el doble debe comportarse como gestor de contexto con `.read()`.
"""
import json
import urllib.error


class FakeHTTPResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def read(self) -> bytes:
        return self._body


def fake_urlopen_json(payload) -> FakeHTTPResponse:
    """Construye un FakeHTTPResponse que devuelve `payload` serializado en JSON."""
    return FakeHTTPResponse(json.dumps(payload).encode("utf-8"))


def raise_http_error(*args, **kwargs):
    raise urllib.error.HTTPError(
        url="https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json",
        code=503,
        msg="Service Unavailable",
        hdrs=None,
        fp=None,
    )


def raise_url_error(*args, **kwargs):
    raise urllib.error.URLError("timed out")
