"""
delay_metrics/handler.py
Lambda disparada por EventBridge cuando se crea un nuevo objeto en S3.
Lee el volcado diario (JSONL: un tren entregado por línea) y publica
métricas de retraso en CloudWatch, una tanda de datapoints por tren.
"""

import json
import logging
import os
import boto3

logger = logging.getLogger("delay_metrics")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

cloudwatch = boto3.client("cloudwatch")
s3 = boto3.client("s3")

NAMESPACE = "ZamoraTrains"
# Límite de la API PutMetricData: máximo 1000 MetricDatum por llamada.
MAX_METRICS_PER_CALL = 1000


def lambda_handler(event, context):
    """
    event: EventBridge 'Object Created' de S3
    {
      "detail": {
        "bucket": {"name": "..."},
        "object": {"key": "zamora-trains/year=.../....jsonl"}
      }
    }
    """
    detail = event.get("detail", {})
    bucket = detail.get("bucket", {}).get("name")
    key = detail.get("object", {}).get("key")

    if not bucket or not key:
        logger.warning("Evento sin bucket/key: %s", event)
        return

    # Solo procesar objetos del datalake (no resultados Athena)
    if not key.startswith("zamora-trains/"):
        return

    # Leer el volcado diario (JSONL: un tren entregado por línea)
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read().decode("utf-8")
    except Exception as exc:
        logger.error("Error leyendo %s/%s: %s", bucket, key, exc)
        return

    records = []
    for line_num, line in enumerate(body.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.error("Línea %d inválida en %s/%s: %s", line_num, bucket, key, exc)

    if not records:
        logger.warning("Sin registros válidos en %s/%s", bucket, key)
        return {"statusCode": 200, "published": 0}

    metric_data = []
    for record in records:
        sentido = record.get("sentido", "Desconocido")
        tipo_dia = record.get("tipo_dia", "Desconocido")

        if record.get("cancelado"):
            # Sin dato real de retraso: se cuenta como cancelación en vez de
            # publicarse en TrainDelayMinutes (evitaría contaminar la media).
            metric_data.append({
                "MetricName": "TrainsCancelled",
                "Dimensions": [{"Name": "Sentido", "Value": sentido}],
                "Value": 1.0,
                "Unit": "Count",
            })
            continue

        delay_minutes = record.get("minutos_retraso", 0)

        metric_data.append({
            "MetricName": "TrainDelayMinutes",
            "Dimensions": [
                {"Name": "Sentido", "Value": sentido},
                {"Name": "TipoDia", "Value": tipo_dia},
            ],
            "Value": float(delay_minutes),
            "Unit": "Count",
        })
        metric_data.append({
            "MetricName": "TrainPassage",
            "Dimensions": [{"Name": "Sentido", "Value": sentido}],
            "Value": 1.0,
            "Unit": "Count",
        })
        if delay_minutes > 0:
            metric_data.append({
                "MetricName": "TrainsWithDelay",
                "Dimensions": [{"Name": "Sentido", "Value": sentido}],
                "Value": 1.0,
                "Unit": "Count",
            })

    for i in range(0, len(metric_data), MAX_METRICS_PER_CALL):
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=metric_data[i:i + MAX_METRICS_PER_CALL],
        )

    logger.info("Métricas publicadas para %d trenes (%s)", len(records), key)
    return {"statusCode": 200, "published": len(records)}
