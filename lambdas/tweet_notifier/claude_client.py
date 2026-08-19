"""
claude_client.py
Redacta el texto de un tuit y sus hashtags a partir de los datos de un tren
con retraso, usando Claude Sonnet 4.6 vía Amazon Bedrock (InvokeModel, sin
el SDK de Anthropic — solo boto3, igual que el resto de este proyecto).

Bedrock no soporta ninguna server-side tool (búsqueda web incluida), así
que las tendencias reales de X se consiguen aparte, vía xfetch_client.py,
como enriquecimiento aditivo y no bloqueante — igual de espíritu que el
enriquecimiento GTFS-RT de train_tracker: si xfetch falla, se sigue
redactando el tuit sin hashtag de tendencia.
"""

import json
import logging
import os

import boto3

import xfetch_client

logger = logging.getLogger(f"tweet_notifier.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

CLAUDE_MODEL_ID = os.environ.get("CLAUDE_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
DELAY_ALERT_THRESHOLD_MINUTES = int(os.environ.get("DELAY_ALERT_THRESHOLD_MINUTES", "15"))
XFETCH_TRENDS_ENABLED = os.environ.get("XFETCH_TRENDS_ENABLED", "true").lower() == "true"
ANTHROPIC_VERSION = "bedrock-2023-05-31"

bedrock_runtime = boto3.client("bedrock-runtime")

ADVOCACY_HASHTAGS = {
    "#ZamoraNecesitaTren", "#TrenMadrugadorYa", "#ZamoraAVE",
    "#AVEZamora", "#ZamoraConecta", "#ZamoraEnUnaHora"
}

GENERIC_HASHTAGS = {
 "#Renfe", "#TrenAVE", "#MovilidadSostenible", "#TransportePublico", "#FerrocarrilEspañol"
}

SYSTEM_PROMPT = f"""Eres el Social Manager en X (Twitter) de la Asociación de \
Usuarios de Trenes AVE de Zamora. Redactas un único tuit (máximo 280 \
caracteres en total, contando el texto y los hashtags) a partir de los \
datos de un tren concreto, con un tono reivindicativo pero riguroso, \
cercano, comparativo y urgente — nunca victimista, siempre basado en \
hechos.

Actores a mencionar cuando encaje de forma natural: @Renfe, @adif_es, el \
Ministerio de Transportes.

El prompt recibe 2 parámetros: `hora_prevista` y `hora_real`. Son las horas de llegada a Destino: 
- A Madrid si el sentido es Madrid
- A Zamora si el sentido es Galicia

Hay tres situaciones posibles, indicadas en el prompt del usuario:

- `tren_madrugador_con_retraso`: el tren es el único tren laborable que \
permite salir de Zamora hacia Madrid por la mañana, y hoy además lleva más \
de 15 minutos de retraso. Reivindica la falta de un tren madrugador útil y menciona que los \
zamoranos llegan a su puesto de trabajo en Madrid una hora tarde, además de los \
minutos de retraso de hoy. Un 20% de las veces puedes indicar que Salamanca, Valladolid y Segovia si que tienen \
un tren madrugador útil, pero en ningún caso en tono victimista.
- `tren_madrugador_puntual`: el mismo tren, pero con 15 minutos de retraso \
o menos. Reivindica igualmente la falta de un tren madrugador útil, \
mencionando solo que los zamoranos ya llegan una hora tarde a su puesto de \
trabajo en Madrid incluso cuando el tren va puntual — sin sumar el \
retraso de hoy, que es mínimo.
- `retraso_generico`: cualquier otro tren con más de 15 minutos de \
retraso. Reivindica un servicio ferroviario de calidad y fiable, para que \
las instituciones no se olviden de Zamora — no menciones el tren \
madrugador en este caso.

Con los 2 casos de tren madrugador, además del mensaje es conveniente mencionar las siguientes cuentas:
- @diputación_de_zamora
- @jcyl
- @minsterio_de_transportes
- @gobierno_de_españa

Hashtags: elige entre 2 y 4, variando entre tuits. Incluye SIEMPRE al \
menos uno de este grupo reivindicativo: {', '.join(ADVOCACY_HASHTAGS)}. Completa con \
hashtags genéricos según encaje: {', '.join(GENERIC_HASHTAGS)}

Si el mensaje del usuario incluye una lista de tendencias actuales en X, \
añade una de esos hastags tendencia, pero escogiendo el que mejor puede encajar de forma \
natural con el mensaje — nunca en sustitución del hashtag reivindicativo \
obligatorio, pero siempre incluir un hashtag tendencia. Si no se incluye ninguna lista,\
no fuerces nada. No es obligatorio usar un hashtag tendencia, no buscamos que se nos acuse de oportunistas o spam

Es importante mencionar que el limite de 280 caracteres es un limite duro, por lo que en la salida, la suma de la \
suma de los campos `tweet_text`y `hastags` no pueden superar los 280 caracteres. El campo `hashtags` debe \
permanecer inmutable, por lo que ajusta el campo `tweet_text` para que tenga una longitud igual o inferior a 275 menos\
La longitud de los hashtags
"""


# ¿Incluir siempre el tuit de tren madrugador?
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "tweet_text": {
            "type": "string",
            "description": "Texto del tuit, sin los hashtags (se añaden aparte).",
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Hashtags a incluir, cada uno con el símbolo # y sin espacios.",
        },
    },
    "required": ["tweet_text", "hashtags"],
    "additionalProperties": False,
}


def _situacion(alert: dict) -> str:
    """Determina qué una de las 3 situaciones del SYSTEM_PROMPT aplica a esta alerta."""
    if not alert.get("es_tren_madrugador"):
        return "retraso_generico"
    if alert["minutos_retraso"] > DELAY_ALERT_THRESHOLD_MINUTES:
        return "tren_madrugador_con_retraso"
    return "tren_madrugador_puntual"


def _build_user_message(alert: dict, trending_hashtags: list) -> str:
    message = (
        f"Situación: {_situacion(alert)}\n"
        f"Tren: {alert['cod_comercial']} (sentido {alert['sentido']})\n"
        f"Hora prevista de llegada: {alert['hora_programada']}\n"
        f"Hora rea de llegadal: {alert['hora_llegada_corregida']}\n"
        f"Minutos de retraso: {alert['minutos_retraso']}\n"
        f"Fecha: {alert['fecha']}\n"
    )
    if trending_hashtags:
        message += f"Tendencias actuales en X (España): {', '.join(trending_hashtags)}\n"
    message += "\nRedacta el tuit y los hashtags según la situación indicada."
    return message


def draft_tweet(alert: dict, log_extra: dict) -> dict:
    """
    Devuelve {"tweet_text": str, "hashtags": [str, ...]} para el tren dado.
    Lanza excepción si Claude no ha podido redactar (refusal u otro
    stop_reason distinto de "end_turn", o una respuesta sin bloque de texto).
    """
    trending_hashtags = xfetch_client.get_trending_hashtags(log_extra) if XFETCH_TRENDS_ENABLED else []
    logger.debug(f'Trending hahses: {trending_hashtags}', extra=log_extra)
    prompt = _build_user_message(alert, trending_hashtags)
    logger.debug(f'Prompt: {prompt}')
    body = json.dumps({
        "anthropic_version": ANTHROPIC_VERSION,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "output_config": {"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        "messages": [{"role": "user", "content": prompt}],
    })

    response = bedrock_runtime.invoke_model(modelId=CLAUDE_MODEL_ID, body=body)
    response_body = json.loads(response["body"].read())

    if response_body.get("stop_reason") != "end_turn":
        raise RuntimeError(
            f"Claude no ha redactado el tuit para {alert.get('cod_comercial')} "
            f"(stop_reason={response_body.get('stop_reason')})"
        )

    text_blocks = [
        block["text"] for block in response_body.get("content", [])
        if block.get("type") == "text"
    ]
    if not text_blocks:
        raise RuntimeError(
            f"Respuesta de Claude sin bloque de texto para {alert.get('cod_comercial')}"
        )

    result = json.loads(text_blocks[-1])
    hashtags = result["hashtags"]
    if ADVOCACY_HASHTAGS.isdisjoint(hashtags):
        logger.warning(
            "Claude no incluyó ningún hashtag reivindicativo para %s; se añade uno por defecto",
            alert.get("cod_comercial"), extra=log_extra
        )
        hashtags.append("#TrenMadrugadorYa")

    return {"tweet_text": result["tweet_text"], "hashtags": hashtags}
