"""Base TestCase para tests de lambdas/api/handler.py con DynamoDB/S3 mockeados vía moto."""
import unittest

from moto import mock_aws

from tests.dummies import api_env
from tests.dummies import aws_resources


class ApiHandlerTestCase(unittest.TestCase):
    """
    Arranca moto, crea la tabla DynamoDB y el bucket S3 con el mismo esquema
    que infrastructure/template.yaml (reutilizando los mismos helpers de
    aws_resources.py que usa HandlerTestCase), e importa lambdas/api/handler.py
    bajo el nombre "api_handler" (ver api_env.import_api_handler) para evitar
    colisionar con el "handler" de train_tracker en sys.modules.
    """

    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.table = aws_resources.create_state_table()
        self.metrics_table = aws_resources.create_metrics_table()
        self.s3 = aws_resources.create_datalake_bucket()

        self.handler = api_env.import_api_handler()

    def put_state_item(self, item: dict) -> None:
        self.table.put_item(Item=item)

    def put_metrics_item(self, item: dict) -> None:
        self.metrics_table.put_item(Item=item)

    def get_item(self, cod: str, fecha_iso: str):
        resp = self.table.get_item(Key={"pk": f"{cod}#{fecha_iso}"})
        return resp.get("Item")

    def put_daily_jsonl(self, key: str, records: list[dict]) -> None:
        """
        Escribe un objeto JSONL directamente en el bucket de test, con el
        mismo formato (una línea = un JSON) que datalake_writer.py, pero sin
        pasar por _build_daily_key del handler bajo test (para no acoplar el
        fixture a la implementación que se está probando).
        """
        import json

        body = "\n".join(json.dumps(record, ensure_ascii=False, default=str) for record in records)
        self.s3.put_object(
            Bucket=api_env.S3_BUCKET_NAME,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/x-ndjson",
        )
