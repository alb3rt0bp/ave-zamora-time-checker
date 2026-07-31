"""
aws_resources.py
Helpers para crear, bajo moto, los recursos AWS con el mismo esquema que
infrastructure/template.yaml (tabla DynamoDB TrainStateTable y bucket S3
DatalakeBucket), listos para que handler.py opere contra ellos.
"""
import boto3

from tests.dummies import aws_env  # noqa: F401 - fuerza el setup de entorno/sys.path


def create_state_table():
    """Crea la tabla DynamoDB de estado con el mismo esquema (clave simple pk) que el template."""
    dynamodb = boto3.resource("dynamodb", region_name=aws_env.AWS_REGION)
    table = dynamodb.create_table(
        TableName=aws_env.DYNAMODB_TABLE_NAME,
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def create_datalake_bucket():
    """Crea el bucket S3 del Data Lake."""
    s3 = boto3.client("s3", region_name=aws_env.AWS_REGION)
    s3.create_bucket(
        Bucket=aws_env.S3_BUCKET_NAME,
        CreateBucketConfiguration={"LocationConstraint": aws_env.AWS_REGION},
    )
    return s3
