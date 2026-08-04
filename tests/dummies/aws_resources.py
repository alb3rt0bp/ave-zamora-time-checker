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


def _create_topic_with_queue(sns, sqs, topic_arn_env_value: str):
    """Crea un topic SNS con una cola SQS suscrita, para poder inspeccionar los mensajes publicados."""
    topic_name = topic_arn_env_value.rsplit(":", 1)[-1]
    topic_arn = sns.create_topic(Name=topic_name)["TopicArn"]

    queue_url = sqs.create_queue(QueueName=f"{topic_name}-test-queue")["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)

    return topic_arn, queue_url


def create_delay_topic():
    """
    Crea el topic SNS de alertas de retraso (mismo ARN que espera
    aws_env.DELAY_ALERT_SNS_TOPIC_ARN) con una cola SQS suscrita, para que
    los tests puedan leer los mensajes que handler.py publica.
    """
    sns = boto3.client("sns", region_name=aws_env.AWS_REGION)
    sqs = boto3.client("sqs", region_name=aws_env.AWS_REGION)
    topic_arn, queue_url = _create_topic_with_queue(sns, sqs, aws_env.DELAY_ALERT_SNS_TOPIC_ARN)
    return sns, sqs, topic_arn, queue_url


def create_data_quality_topic():
    """
    Crea el topic SNS de alertas de calidad de dato (mismo ARN que espera
    aws_env.DATA_QUALITY_ALERT_SNS_TOPIC_ARN) con una cola SQS suscrita, para
    que los tests puedan leer los mensajes que _publish_negative_delay_alert
    publica.
    """
    sns = boto3.client("sns", region_name=aws_env.AWS_REGION)
    sqs = boto3.client("sqs", region_name=aws_env.AWS_REGION)
    topic_arn, queue_url = _create_topic_with_queue(sns, sqs, aws_env.DATA_QUALITY_ALERT_SNS_TOPIC_ARN)
    return sns, sqs, topic_arn, queue_url
