"""Base TestCase para tests que necesitan handler.py con DynamoDB/S3/SNS mockeados vía moto."""
import json
import unittest

from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies import aws_resources


class HandlerTestCase(unittest.TestCase):
    """
    Arranca moto, crea la tabla DynamoDB, el bucket S3 y el topic SNS de
    alertas de retraso (con una cola SQS suscrita, para poder inspeccionar
    los mensajes publicados) con el mismo esquema que
    infrastructure/template.yaml, e importa handler.py. El módulo solo se
    importa de verdad una vez por proceso (Python cachea imports), pero eso
    no es un problema: moto intercepta las llamadas AWS en el momento en que
    se hacen, no en el momento en que se crea el cliente/recurso boto3.
    """

    def setUp(self):
        self.mock_aws = mock_aws()
        self.mock_aws.start()
        self.addCleanup(self.mock_aws.stop)

        self.table = aws_resources.create_state_table()
        self.s3 = aws_resources.create_datalake_bucket()
        self.sns, self.sqs, self.delay_topic_arn, self.delay_queue_url = aws_resources.create_delay_topic()

        import handler
        self.handler = handler

    def get_item(self, cod: str, fecha_iso: str):
        resp = self.table.get_item(Key={"pk": f"{cod}#{fecha_iso}"})
        return resp.get("Item")

    def get_published_delay_alerts(self) -> list[dict]:
        """Lee (y consume) los mensajes publicados en el topic de alertas de retraso."""
        resp = self.sqs.receive_message(
            QueueUrl=self.delay_queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=0
        )
        alerts = []
        for message in resp.get("Messages", []):
            body = json.loads(message["Body"])
            alerts.append(json.loads(body["Message"]))
        return alerts
