"""
claude_client.py
Redacta el texto de un tuit y sus hashtags a partir de los datos de un tren
con retraso, usando Claude Sonnet 5 vía Amazon Bedrock (InvokeModel, sin
el SDK de Anthropic — solo boto3, igual que el resto de este proyecto).

Bedrock no soporta ninguna server-side tool (búsqueda web incluida), así
que las tendencias reales de X se consiguen aparte, vía trends_reader.py
(que lee lo último guardado en S3 por la lambda trend_fetcher, en vez de
golpear xfetch.io en cada tuit), como enriquecimiento aditivo y no
bloqueante — igual de espíritu que el enriquecimiento GTFS-RT de
train_tracker: si no hay tendencias disponibles, se sigue redactando el
tuit sin hashtag de tendencia.
"""

import json
import logging
import os

import boto3

import trends_reader

logger = logging.getLogger(f"tweet_notifier.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

CLAUDE_MODEL_ID = os.environ.get("CLAUDE_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
DELAY_ALERT_THRESHOLD_MINUTES = int(os.environ.get("DELAY_ALERT_THRESHOLD_MINUTES", "15"))
TRENDS_ENABLED = os.environ.get("TRENDS_ENABLED", "true").lower() == "true"
ANTHROPIC_VERSION = "bedrock-2023-05-31"
MAX_TWEET_LENGTH = 350

bedrock_runtime = boto3.client("bedrock-runtime")

ADVOCACY_HASHTAGS = {
    "#ZamoraNecesitaTren", "#TrenMadrugadorYa", "#ZamoraAVE",
    "#AVEZamora", "#ZamoraConecta", "#ZamoraEnUnaHora"
}

GENERIC_HASHTAGS = {
 "#Renfe", "#TrenAVE", "#MovilidadSostenible", "#TransportePublico", "#FerrocarrilEspañol"
}

SYSTEM_PROMPT = f"""Eres el Social Manager en X (Twitter) de la Asociación de 
Usuarios de Trenes de Zamora. Redactas un único tuit (máximo 280 \
caracteres en total, contando el texto y los hashtags) a partir de los \
datos de un tren concreto, con un tono reivindicativo pero riguroso, \
cercano, comparativo y urgente — nunca victimista, siempre basado en \
hechos.

Actores a mencionar cuando encaje de forma natural:
- @Renfe (Operadora de servicios ferroviarios)
- @Adif_es (Gestora de infraestructuras ferroviarias)
- @transportesgob (Ministerio Transportes y Movilidad Sostenible)

El prompt recibe 2 parámetros: `hora_prevista` y `hora_real`. Son las horas de llegada a Destino: 
- A Madrid si el sentido es Madrid, trayecto Zamora->Madrid
- A Zamora si el sentido es Galicia, trayecto Madrid->Zamora

Hay tres situaciones posibles, indicadas en el prompt del usuario:

- `tren_madrugador_con_retraso`: el tren es el primer tren laborable que \
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
- @dipuzamora (Diputación de Zamora)
- @jcyl (Junta de Comunidades de Castilla y León)
- @transportesgob (Ministerio Transportes y Movilidad Sostenible)
- @desdelamoncloa (Cuenta oficial del Gobierno de España)

Hashtags: elige entre 2 y 4, variando entre tuits. Incluye SIEMPRE al \
menos uno de este grupo reivindicativo: {', '.join(ADVOCACY_HASHTAGS)}. Completa con \
hashtags genéricos según encaje: {', '.join(GENERIC_HASHTAGS)}

## Pautas para la elección de hashtags
Si el mensaje del usuario incluye una lista de tendencias actuales en X, añade como hashtag adicional \
como MUCHO una tendencia — nunca en sustitución del hashtag reivindicativo obligatorio.

Al seleccionar hashtags para un post, sigue este criterio de forma estricta:

### 1. Relevancia temática obligatoria
Un hashtag solo es válido si cumple AL MENOS una de estas condiciones:
- Es propio de la causa/marca (ej. hashtags de campaña definidos en el contexto)
- Es un término genérico de la temática general (ej. sector, industria, tipo de contenido)
- Es un trending topic **cuyo contenido real** (no solo el nombre) se relaciona con el tema del post

**Nunca** uses un hashtag trending solo porque tiene volumen alto, si no tiene relación temática real con el contenido del post.

### 2. Verificación antes de recomendar un trending topic
Antes de sugerir un hashtag que esté en tendencia:
- Identifica de qué trata realmente (programa de TV, evento deportivo, serie, noticia, día genérico de la semana, etc.)
- Si no puedes determinar el origen o contexto del hashtag con confianza, indícalo explícitamente en vez de asumir que es aprovechable
- Si el trending pertenece a contenido de entretenimiento (reality, serie, docu-reality, programa de TV con audiencia no relacionada), descártalo salvo que el post haga referencia explícita y legítima a ese contenido

### 3. Días genéricos como opción segura por defecto
Los hashtags de "día de la semana" genéricos (#FelizLunes, #FelizMartes, etc.) son válidos como opción de bajo riesgo cuando:
- No hay ningún trending topic temáticamente alineado disponible
- Se usan como complemento, no como sustituto de los hashtags propios de la causa

### 4. Límite de cantidad
- Recomienda un máximo de 2-4 hashtags por post
- Prioriza 1 hashtag propio de marca/campaña + 1-2 hashtags de alcance (genéricos o trending relevantes)
- Nunca satures un post con 5+ hashtags: reduce alcance orgánico y aparenta spam

### 5. Transparencia sobre limitaciones de datos
Si no tienes acceso a datos de tendencias en tiempo real fiables (o las fuentes disponibles son contradictorias o de fecha incierta):
- Indícalo explícitamente al usuario
- No presentes datos de tendencias como definitivos si provienen de fuentes de scraping de terceros no oficiales
- Sugiere al usuario verificar directamente en la app de X cuando la precisión al minuto sea crítica

### 6. Nunca recomendar por inercia
No repitas automáticamente los mismos hashtags de publicaciones anteriores solo por comodidad. Evalúa cada post de forma independiente: el contexto, la actualidad y los trending topics cambian a diario.

## Cálculo EXACTO del límite de 280 caracteres 
LÍMITE DURO, no orientativo, se descarta cualquier \
respuesta que lo supere: al publicarse, el tuit final se compone como `tweet_text` + dos saltos de \
línea (2 caracteres) + los elementos de `hashtags` unidos por un espacio simple. Es decir:

longitud_total = longitud(tweet_text) + 2 + longitud(" ".join(hashtags))

longitud_total no puede superar 280 en ningún caso. Antes de responder, calcula longitud_total mentalmente \
y, si se pasa, recorta `tweet_text` — nunca los hashtags — hasta que quepa. Las cuentas mencionadas \
(@Renfe, @Adif_es, etc.) forman parte de `tweet_text` y cuentan como texto normal, carácter a carácter, \
sin ningún acortamiento automático: inclúyelas en el cálculo igual que el resto del mensaje.

El campo `hashtags` es el que tú eliges libremente (ver instrucciones de hashtags más arriba) SALVO cuando \
el mensaje del usuario indique explícitamente que ya hay unos hashtags fijados que no deben cambiar (esto \
ocurre solo cuando se te pide acortar un tuit ya redactado que superó el límite) — en ese caso, y solo en \
ese caso, devuelve `hashtags` exactamente igual a como se te dio y ajusta únicamente `tweet_text`.
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


def tweet_length(tweet_text: str, hashtags: list) -> int:
    """Longitud total del tuit tal y como se publica: texto + línea en blanco + hashtags."""
    return len(f"{tweet_text}\n\n{' '.join(hashtags)}")


def _invoke_claude(body: str, cod_comercial: str | None) -> dict:
    """
    Llama a Bedrock y devuelve el {tweet_text, hashtags} redactado por Claude.
    Lanza excepción si Claude no ha podido redactar (refusal u otro
    stop_reason distinto de "end_turn", o una respuesta sin bloque de texto).
    """
    response = bedrock_runtime.invoke_model(modelId=CLAUDE_MODEL_ID, body=body)
    response_body = json.loads(response["body"].read())

    if response_body.get("stop_reason") != "end_turn":
        raise RuntimeError(
            f"Claude no ha redactado el tuit para {cod_comercial} "
            f"(stop_reason={response_body.get('stop_reason')})"
        )

    text_blocks = [
        block["text"] for block in response_body.get("content", [])
        if block.get("type") == "text"
    ]
    if not text_blocks:
        raise RuntimeError(f"Respuesta de Claude sin bloque de texto para {cod_comercial}")

    return json.loads(text_blocks[-1])


def draft_tweet(alert: dict, log_extra: dict) -> dict:
    """Devuelve {"tweet_text": str, "hashtags": [str, ...]} para el tren dado."""
    trending_hashtags = trends_reader.get_trending_hashtags(log_extra) if TRENDS_ENABLED else []
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

    result = _invoke_claude(body, alert.get("cod_comercial"))
    hashtags = result["hashtags"]
    if ADVOCACY_HASHTAGS.isdisjoint(hashtags):
        logger.warning(
            "Claude no incluyó ningún hashtag reivindicativo para %s; se añade uno por defecto",
            alert.get("cod_comercial"), extra=log_extra
        )
        hashtags.append("#TrenMadrugadorYa")

    return {"tweet_text": result["tweet_text"], "hashtags": hashtags}


def refine_tweet(alert: dict, drafted: dict, log_extra: dict) -> dict:
    """
    Pide a Claude que reescriba únicamente `tweet_text`, más corto, para que
    el tuit completo quepa en MAX_TWEET_LENGTH caracteres. Los hashtags ya
    elegidos por draft_tweet se dejan intactos — solo se cuentan para
    calcular el presupuesto de caracteres disponible para el texto.
    """
    hashtags = drafted["hashtags"]
    current_length = tweet_length(drafted["tweet_text"], hashtags)
    text_budget = MAX_TWEET_LENGTH - len(f"\n\n{' '.join(hashtags)}")
    prompt = (
        f"El tuit que has redactado para el tren {alert.get('cod_comercial')} ocupa "
        f"{current_length} caracteres y supera el límite de {MAX_TWEET_LENGTH}.\n"
        f"tweet_text actual: {drafted['tweet_text']}\n"
        f"Los hashtags ya están decididos y no deben cambiar: {' '.join(hashtags)}\n"
        f"Redacta de nuevo únicamente el campo tweet_text, manteniendo el mensaje y el "
        f"tono, de forma que no supere los {text_budget} caracteres (así el texto y los "
        f"hashtags juntos quepan en {MAX_TWEET_LENGTH}). Devuelve también el campo "
        f"hashtags, sin modificarlo."
    )
    body = json.dumps({
        "anthropic_version": ANTHROPIC_VERSION,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "output_config": {"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        "messages": [{"role": "user", "content": prompt}],
    })

    result = _invoke_claude(body, alert.get("cod_comercial"))
    refined = {"tweet_text": result["tweet_text"], "hashtags": hashtags}
    logger.info(
        "Tuit para %s refinado: %d -> %d caracteres",
        alert.get("cod_comercial"), current_length,
        tweet_length(refined["tweet_text"], hashtags), extra=log_extra,
    )
    return refined
