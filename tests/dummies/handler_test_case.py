"""Base TestCase para tests que necesitan handler.py con DynamoDB/S3 mockeados vía moto."""
import unittest

from moto import mock_aws

from tests.dummies import aws_env  # noqa: F401 - sys.path/env setup
from tests.dummies import aws_resources


class HandlerTestCase(unittest.TestCase):
    """
    Arranca moto, crea la tabla DynamoDB y el bucket S3 con el mismo esquema
    que infrastructure/template.yaml, e importa handler.py. El módulo solo se
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

        import handler
        self.handler = handler

    def get_item(self, cod: str, fecha_iso: str):
        resp = self.table.get_item(Key={"pk": f"{cod}#{fecha_iso}"})
        return resp.get("Item")
