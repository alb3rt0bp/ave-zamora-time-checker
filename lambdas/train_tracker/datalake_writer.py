"""
datalake_writer.py
Escribe el volcado diario de trenes en S3 con particionado Hive-compatible
para que AWS Glue y Athena puedan descubrirlo automáticamente.

Estructura en S3:
  s3://<bucket>/zamora-trains/
    year=2024/
      month=11/
        day=15/
          2024-11-15.jsonl

Un único fichero por día: JSONL (un objeto JSON por línea, uno por tren
entregado ese día), para minimizar el número de objetos y el overhead de
lectura en Athena (sin capa gratuita).
"""

import json
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

S3_PREFIX = "zamora-trains"


class DatalakeWriter:
    def __init__(self, s3_client, bucket: str, log_extra):
        self.s3 = s3_client
        self.bucket = bucket
        self.log_extra = log_extra

    def write_daily_batch(self, records: list[dict], day: date) -> str:
        """
        Escribe todos los registros del día en un único fichero JSONL.
        Devuelve la S3 key del objeto creado.
        """
        key = self._build_daily_key(day)

        body = "\n".join(json.dumps(record, ensure_ascii=False, default=str) for record in records)

        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/x-ndjson",
            Metadata={"trenes": str(len(records))},
        )

        logger.info(
            "S3 put_object: s3://%s/%s (%d trenes)", self.bucket, key, len(records), extra=self.log_extra
        )
        return key

    def _build_daily_key(self, day: date) -> str:
        """
        Construye la clave S3 con particionado Hive.
        Ejemplo: zamora-trains/year=2024/month=11/day=15/2024-11-15.jsonl
        """
        year  = day.strftime("%Y")
        month = day.strftime("%m")
        day_s = day.strftime("%d")

        return (
            f"{S3_PREFIX}/"
            f"year={year}/month={month}/day={day_s}/"
            f"{day.isoformat()}.jsonl"
        )
