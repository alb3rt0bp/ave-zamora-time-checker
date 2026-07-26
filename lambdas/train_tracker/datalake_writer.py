"""
datalake_writer.py
Escribe eventos de paso de tren en S3 con particionado Hive-compatible
para que AWS Glue y Athena puedan descubrirlos automáticamente.

Estructura en S3:
  s3://<bucket>/zamora-trains/
    year=2024/
      month=11/
        day=15/
          04154_Madrid_20241115T074123.json
          04114_Madrid_20241115T083956.json
          ...

Cada fichero es un JSON de una sola línea (JSONL compatible) con el registro
del evento de paso.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

S3_PREFIX = "zamora-trains"


class DatalakeWriter:
    def __init__(self, s3_client, bucket: str, log_extra):
        self.s3 = s3_client
        self.bucket = bucket
        self.log_extra = log_extra

    def write(self, record: dict, timestamp: datetime) -> str:
        """
        Escribe el registro en S3.
        Devuelve la S3 key del objeto creado.
        """
        key = self._build_key(record["cod_comercial"], record["sentido"], timestamp)

        body = json.dumps(record, ensure_ascii=False, default=str)

        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
            # Metadatos para facilitar búsquedas sin leer el objeto
            Metadata={
                "cod-comercial": record["cod_comercial"],
                "sentido":       record["sentido"],
                "tipo-dia":      record["tipo_dia"],
                "retraso-min":   str(record.get("minutos_retraso", 0)),
            },
        )

        logger.info("S3 put_object: s3://%s/%s", self.bucket, key, extra=self.log_extra)
        return key

    def _build_key(self, cod: str, sentido: str, ts: datetime) -> str:
        """
        Construye la clave S3 con particionado Hive.
        Ejemplo: zamora-trains/year=2024/month=11/day=15/04154_Madrid_20241115T074123.json
        """
        year  = ts.strftime("%Y")
        month = ts.strftime("%m")
        day   = ts.strftime("%d")
        ts_str = ts.strftime("%Y%m%dT%H%M%S")

        return (
            f"{S3_PREFIX}/"
            f"year={year}/month={month}/day={day}/"
            f"{cod}_{sentido}_{ts_str}.json"
        )

    def batch_write(self, records: list[dict], timestamp: datetime) -> list[str]:
        """Escribe múltiples registros y devuelve las keys creadas."""
        keys = []
        for record in records:
            try:
                key = self.write(record, timestamp)
                keys.append(key)
            except Exception as exc:
                logger.error("Error escribiendo %s: %s", record.get("event_id"), exc, extra=self.log_extra)
        return keys
