"""Payloads de ejemplo que devolvería la API de tendencias de xfetch.io."""

# Respuesta real capturada de https://api.xfetch.io/v1/trends (España, 2026-08-07).
# Incluye entradas duplicadas ("Rodri" x3) y tendencias sin '#' inicial, tal
# y como las devuelve xfetch.io de verdad — get_trending_hashtags debe
# filtrar solo las que empiezan por '#', duplicados incluidos.
TRENDS_SPAIN_REAL_SAMPLE = {
    "data": [
        {"trend_name": "Rodri"},
        {"trend_name": "Rodri"},
        {"trend_name": "Rodri"},
        {"trend_name": "Florentino"},
        {"trend_name": "Valverde"},
        {"trend_name": "Diomande"},
        {"trend_name": "#ArianaxFNAC"},
        {"trend_name": "Vinicius"},
        {"trend_name": "Bernardo"},
        {"trend_name": "Barcelona"},
        {"trend_name": "Bernal"},
        {"trend_name": "#7AgostoESP"},
        {"trend_name": "Kroos"},
        {"trend_name": "Riquelme"},
        {"trend_name": "Mourinho"},
        {"trend_name": "#This_And_That"},
        {"trend_name": "De Jong"},
        {"trend_name": "Zubimendi"},
        {"trend_name": "#LaHora7A"},
        {"trend_name": "Wharton"},
    ],
    "meta": {
        "request_id": "req_MhnAM4wzwJi2CG8_",
        "credits": {"charged": 21, "remaining": 741},
    },
}
