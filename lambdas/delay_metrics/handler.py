"""
delay_metrics/handler.py
Lambda disparada por EventBridge cuando se crea un nuevo objeto en S3.
Lee el registro JSON y publica métricas de retraso en CloudWatch.
"""

import json
import logging
import os
import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

cloudwatch = boto3.client("cloudwatch")
s3 = boto3.client("s3")

NAMESPACE = "ZamoraTrains"


def lambda_handler(event, context):
    """
    event: EventBridge 'Object Created' de S3
    {
      "detail": {
        "bucket": {"name": "..."},
        "object": {"key": "zamora-trains/year=.../...json"}
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

    # Leer el registro desde S3
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        record = json.loads(response["Body"].read().decode("utf-8"))
    except Exception as exc:
        logger.error("Error leyendo %s/%s: %s", bucket, key, exc)
        return

    delay_minutes = record.get("minutos_retraso", 0)
    sentido = record.get("sentido", "Desconocido")
    tipo_dia = record.get("tipo_dia", "Desconocido")
    cod_comercial = record.get("cod_comercial", "UNKNOWN")

    logger.info("Tren %s | %s | retraso: %d min", cod_comercial, sentido, delay_minutes)

    # Publicar métricas
    metric_data = [
        {
            "MetricName": "TrainDelayMinutes",
            "Dimensions": [
                {"Name": "Sentido", "Value": sentido},
                {"Name": "TipoDia", "Value": tipo_dia},
            ],
            "Value": float(delay_minutes),
            "Unit": "Count",
        },
        {
            "MetricName": "TrainPassage",
            "Dimensions": [
                {"Name": "Sentido", "Value": sentido},
            ],
            "Value": 1.0,
            "Unit": "Count",
        },
    ]

    # Métrica adicional si hay retraso
    if delay_minutes > 0:
        metric_data.append({
            "MetricName": "TrainsWithDelay",
            "Dimensions": [
                {"Name": "Sentido", "Value": sentido},
            ],
            "Value": 1.0,
            "Unit": "Count",
        })

    cloudwatch.put_metric_data(
        Namespace=NAMESPACE,
        MetricData=metric_data,
    )

    logger.info("Métricas publicadas para %s", cod_comercial)
    return {"statusCode": 200}
