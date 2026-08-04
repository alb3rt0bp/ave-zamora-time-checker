"""Payloads de ejemplo que devolvería la API de Renfe (flotaLD.json)."""

# Tren M100 aún no ha pasado por Zamora ni ha llegado a Chamartín.
TRAIN_M100_EN_RUTA = {
    "codComercial": "M100",
    "idTren": "1",
    "codEstAnt": "10000",
    "codEstSig": "20000",
    "ultRetraso": 0,
    "lat": 41.5,
    "lon": -5.7,
}

# Tren M100 acaba de pasar por Zamora.
TRAIN_M100_EN_ZAMORA = {
    "codComercial": "M100",
    "idTren": "1",
    "codEstAnt": "30200",  # ZAMORA_CODE
    "codEstSig": "40000",
    "ultRetraso": 3,
    "lat": 41.5034,
    "lon": -5.7447,
}

# Tren M100 acaba de llegar a Chamartín.
TRAIN_M100_EN_CHAMARTIN = {
    "codComercial": "M100",
    "idTren": "1",
    "codEstAnt": "17000",  # CHAMARTIN_CODE
    "codEstSig": "",
    "ultRetraso": 5,
    "lat": 40.472,
    "lon": -3.682,
}

# Tren G100 aún no ha pasado por Zamora.
TRAIN_G100_EN_RUTA = {
    "codComercial": "G100",
    "idTren": "2",
    "codEstAnt": "10000",
    "codEstSig": "30200",
    "ultRetraso": 2,
    "lat": 41.4,
    "lon": -5.6,
}

# Tren G100 acaba de pasar por Zamora.
TRAIN_G100_EN_ZAMORA = {
    "codComercial": "G100",
    "idTren": "2",
    "codEstAnt": "30200",  # ZAMORA_CODE
    "codEstSig": "40000",
    "ultRetraso": 4,
    "lat": 41.5034,
    "lon": -5.7447,
}

# Tren G100 acaba de pasar por Zamora con un retraso importante (> 15 min),
# para probar la alerta de retraso en SNS (_maybe_publish_delay_alert).
TRAIN_G100_EN_ZAMORA_CON_RETRASO = {
    **TRAIN_G100_EN_ZAMORA,
    "ultRetraso": 20,
}

# Tren M100 acaba de llegar a Chamartín con un retraso importante (> 15 min).
TRAIN_M100_EN_CHAMARTIN_CON_RETRASO = {
    **TRAIN_M100_EN_CHAMARTIN,
    "ultRetraso": 30,
}

# Tren G100 acaba de pasar por Zamora con un ultRetraso disparatado
# (bug real observado en la API de Renfe), para probar _sanitize_retraso.
TRAIN_G100_EN_ZAMORA_CON_RETRASO_NEGATIVO_ANOMALO = {
    **TRAIN_G100_EN_ZAMORA,
    "ultRetraso": -562,
}

# Tren M100 acaba de llegar a Chamartín con un ultRetraso disparatado
# (bug real observado en la API de Renfe), para probar _sanitize_retraso.
TRAIN_M100_EN_CHAMARTIN_CON_RETRASO_NEGATIVO_ANOMALO = {
    **TRAIN_M100_EN_CHAMARTIN,
    "ultRetraso": -562,
}

FLOTA_RESPONSE_SAMPLE = [TRAIN_M100_EN_RUTA, TRAIN_G100_EN_RUTA]

TRENES_CON_ESTACIONES_SAMPLE = {
    "trenes": [
        {"codComercial": "M100", "estaciones": [{"codigo": "10000", "hora": "07:00"}]},
    ]
}
