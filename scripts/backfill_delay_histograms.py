#!/usr/bin/env python3
"""
backfill_delay_histograms.py
Siembra histograma_retraso ({minutos_retraso -> nº de viajes}) en los items
TRAIN# de TrainMetricsTable a partir de todo el histórico ya volcado en el
Data Lake S3.

Necesario porque los días agregados ANTES de que metrics_writer empezase a
acumular el histograma quedaron sin él, y scripts/backfill_metrics.py no
puede recuperarlos: su guarda de idempotencia (last_aggregated_date) hace
que reprocesar un día ya agregado sea un no-op deliberado.

A diferencia de backfill_metrics.py, este script NO acumula: recalcula el
histograma completo desde cero leyendo todos los JSONL y lo SOBRESCRIBE.
Eso lo hace idempotente por construcción — se puede ejecutar las veces que
haga falta, y también después de que el pipeline diario ya haya añadido días
nuevos, porque esos días están igualmente en S3 y entran en el recálculo.
El resto de contadores del item (los 4 tramos, last_aggregated_date...) no
se tocan.

Conviene no lanzarlo justo a las 02:15 (hora de daily_dump_handler): si el
volcado del día escribe entre la lectura de S3 y la escritura en DynamoDB,
ese día quedaría fuera del histograma hasta la siguiente ejecución.

Uso: apunta las mismas variables de entorno que usan las Lambdas a los
recursos ya desplegados, con credenciales AWS válidas (perfil/rol con
permiso de lectura en el bucket y lectura+escritura en la tabla):

  DATALAKE_S3_BUCKET=zamora-trains-datalake-prod-<account-id> \
  DYNAMODB_METRICS_TABLE=zamora-train-metrics-prod \
  python3 scripts/backfill_delay_histograms.py

Con --dry-run imprime lo que escribiría (incluida la mediana y los
percentiles resultantes) sin tocar DynamoDB.
"""

import json
import logging
import os
import sys

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_delay_histograms")

S3_PREFIX = "zamora-trains"


def _iter_daily_jsonl_keys(s3, bucket: str) -> list[str]:
    paginator = s3.get_paginator("list_objects_v2")
    return sorted(
        obj["Key"]
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{S3_PREFIX}/")
        for obj in page.get("Contents", [])
        if obj["Key"].endswith(".jsonl")
    )


def _load_records(s3, bucket: str, key: str) -> list[dict]:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def build_histograms(records: list[dict]) -> dict[str, dict[str, int]]:
    """
    {cod_comercial -> {minutos_retraso -> nº de viajes}} para todos los
    registros del histórico. Se excluyen los cancelados y los que no tengan
    minutos_retraso, igual que hace MetricsWriter: un tren que no circuló no
    debe contar como "llegó con 0 minutos de retraso".
    """
    histograms: dict[str, dict[str, int]] = {}
    for record in records:
        if record.get("cancelado") or record.get("minutos_retraso") is None:
            continue
        histogram = histograms.setdefault(record["cod_comercial"], {})
        key = str(record["minutos_retraso"])
        histogram[key] = histogram.get(key, 0) + 1
    return histograms


def _percentiles(histogram: dict[str, int]) -> str:
    """Resumen legible para el log — mismo criterio de rango más cercano que la API."""
    values = sorted(minute for k, count in histogram.items() for minute in [int(k)] * count)
    def p(q):
        return values[min(len(values) - 1, round(q * (len(values) - 1)))]
    return f"P25={p(.25)} mediana={p(.50)} P75={p(.75)} P90={p(.90)}"


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    bucket = os.environ["DATALAKE_S3_BUCKET"]
    metrics_table_name = os.environ["DYNAMODB_METRICS_TABLE"]

    s3 = boto3.client("s3")
    metrics_table = boto3.resource("dynamodb").Table(metrics_table_name)

    keys = _iter_daily_jsonl_keys(s3, bucket)
    logger.info("Encontrados %d volcados diarios en s3://%s/%s/", len(keys), bucket, S3_PREFIX)

    records = [record for key in keys for record in _load_records(s3, bucket, key)]
    histograms = build_histograms(records)
    logger.info("%d registros leídos, %d trenes con histograma", len(records), len(histograms))

    written, skipped = 0, 0
    for cod, histogram in sorted(histograms.items()):
        total = sum(histogram.values())
        pk = f"TRAIN#{cod}"
        item = metrics_table.get_item(Key={"pk": pk}).get("Item")
        if item is None:
            # El item lo crea metrics_writer con el resto de contadores; sin
            # él no hay dónde colgar el histograma. Ejecuta antes
            # backfill_metrics.py.
            logger.warning("%s no existe en la tabla — ejecuta antes backfill_metrics.py", pk)
            skipped += 1
            continue

        logger.info("%s: %d viajes, %s%s", pk, total, _percentiles(histogram), " (dry-run)" if dry_run else "")
        if not dry_run:
            metrics_table.update_item(
                Key={"pk": pk},
                UpdateExpression="SET histograma_retraso = :h",
                ExpressionAttributeValues={":h": histogram},
            )
            written += 1

    logger.info("Backfill completado: %d items escritos, %d omitidos.", written, skipped)


if __name__ == "__main__":
    main()
