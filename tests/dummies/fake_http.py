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


def fake_urlopen_by_url(url_to_payload: dict):
    """
    side_effect para @patch("urllib.request.urlopen") que despacha una
    respuesta JSON distinta según la URL de la petición (inspecciona
    req.full_url buscando cada fragmento de `url_to_payload` como substring).
    Necesario en tests que, dentro de una misma llamada a lambda_handler(),
    acceden a más de un endpoint — p. ej. flotaLD.json (RenfeClient) y
    trip_updates_LD.json (GtfsRtClient) cuando el enriquecimiento GTFS-RT
    está activado — y por tanto no pueden usar un único mock_urlopen.return_value.
    """
    def _side_effect(req, timeout=None):
        for url_fragment, payload in url_to_payload.items():
            if url_fragment in req.full_url:
                return fake_urlopen_json(payload)
        raise AssertionError(f"URL inesperada en fake_urlopen_by_url: {req.full_url}")

    return _side_effect


def fake_urlopen_dispatch(url_to_response: dict):
    """
    Como fake_urlopen_by_url, pero despachando una respuesta YA construida
    (típicamente un FakeHTTPResponse) en vez de serializar siempre a JSON —
    necesario cuando alguna de las URLs no devuelve JSON (p. ej. el zip GTFS
    de gtfs_client.py, mientras otra URL en la misma llamada sí lo hace).
    """
    def _side_effect(req, timeout=None):
        for url_fragment, response in url_to_response.items():
            if url_fragment in req.full_url:
                return response
        raise AssertionError(f"URL inesperada en fake_urlopen_dispatch: {req.full_url}")

    return _side_effect
