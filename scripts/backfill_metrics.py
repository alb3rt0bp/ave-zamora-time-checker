#!/usr/bin/env python3
"""
backfill_metrics.py
Reprocesa el histórico ya volcado en el Data Lake S3 (zamora-trains/year=*/
month=*/day=*/*.jsonl) contra MetricsWriter.update_daily_metrics, en orden
cronológico, para que TrainMetricsTable (TRAIN#/WEEK#/MONTH#/GLOBAL)
refleje el histórico real en vez de arrancar vacía el día del despliegue.

Seguro de ejecutar más de una vez, o sobre días ya agregados: la guarda de
idempotencia de MetricsWriter (last_aggregated_date) hace que reprocesar un
día ya agregado sea un no-op.

Uso: apunta las mismas variables de entorno que usan las Lambdas a los
recursos ya desplegados, con credenciales AWS válidas (perfil/rol con
permiso de lectura en el bucket y lectura+escritura en la tabla):

  DATALAKE_S3_BUCKET=zamora-trains-datalake-prod-<account-id> \
  DYNAMODB_METRICS_TABLE=zamora-train-metrics-prod \
  SIGNIFICANT_DELAY_THRESHOLD_MINUTES=15 \
  python3 scripts/backfill_metrics.py
"""

import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).parent.parent / "lambdas" / "train_tracker"))
from metrics_writer import MetricsWriter  # noqa: E402 - requiere el sys.path anterior

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_metrics")

S3_PREFIX = "zamora-trains"


def _iter_daily_jsonl_keys(s3, bucket: str) -> list[str]:
    """
    Todas las claves S3 de volcados diarios, en orden cronológico. El nombre
    de fichero (YYYY-MM-DD.jsonl) ya ordena cronológicamente como string,
    así que un sort simple basta — no hace falta parsear las particiones
    year=/month=/day= del path.
    """
    paginator = s3.get_paginator("list_objects_v2")
    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{S3_PREFIX}/")
        for obj in page.get("Contents", [])
        if obj["Key"].endswith(".jsonl")
    ]
    return sorted(keys)


def _target_date_from_key(key: str) -> date:
    """"zamora-trains/year=2026/month=07/day=31/2026-07-31.jsonl" -> date(2026,7,31)."""
    filename = key.rsplit("/", 1)[-1]
    return date.fromisoformat(filename.removesuffix(".jsonl"))


def _load_records(s3, bucket: str, key: str) -> list[dict]:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def main() -> None:
    bucket = os.environ["DATALAKE_S3_BUCKET"]
    metrics_table_name = os.environ["DYNAMODB_METRICS_TABLE"]
    threshold_minutes = int(os.environ.get("SIGNIFICANT_DELAY_THRESHOLD_MINUTES", "15"))

    s3 = boto3.client("s3")
    metrics_table = boto3.resource("dynamodb").Table(metrics_table_name)
    writer = MetricsWriter(metrics_table, threshold_minutes, {"span_id": "backfill"})

    keys = _iter_daily_jsonl_keys(s3, bucket)
    logger.info("Encontrados %d volcados diarios en s3://%s/%s/", len(keys), bucket, S3_PREFIX)

    now = datetime.now(timezone.utc)
    for key in keys:
        target_date = _target_date_from_key(key)
        records = _load_records(s3, bucket, key)
        writer.update_daily_metrics(records, target_date, now)
        logger.info("Reprocesado %s (%d registros) — %s", target_date.isoformat(), len(records), key)

    logger.info("Backfill completado: %d días procesados.", len(keys))


if __name__ == "__main__":
    main()
