"""
aws_env.py
Prepara el entorno para poder importar los módulos de lambdas/train_tracker
fuera del runtime real de AWS Lambda:
  - añade lambdas/train_tracker a sys.path (imports planos, igual que hace
    el propio paquete desplegado por SAM: from renfe_client import ...)
  - define las variables de entorno que handler.py exige a nivel de módulo
  - configura credenciales AWS ficticias para moto

Debe importarse ANTES de importar cualquier módulo de lambdas/train_tracker
(handler, renfe_client, schedule_matcher, datalake_writer).
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRAIN_TRACKER_DIR = os.path.join(REPO_ROOT, "lambdas", "train_tracker")
DUMMIES_DIR = os.path.dirname(os.path.abspath(__file__))

if TRAIN_TRACKER_DIR not in sys.path:
    sys.path.insert(0, TRAIN_TRACKER_DIR)

# Credenciales ficticias: moto no las valida, pero botocore exige que existan.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-south-2")

# Variables de entorno que handler.py lee a nivel de módulo (import time).
os.environ.setdefault("DATALAKE_S3_BUCKET", "test-zamora-datalake")
os.environ.setdefault("DYNAMODB_STATE_TABLE", "test-zamora-train-state")
os.environ.setdefault(
    "SCHEDULES_FILE", os.path.join(DUMMIES_DIR, "train_schedules_sample.json")
)
os.environ.setdefault("ZAMORA_STATION_CODE", "30200")
os.environ.setdefault("CHAMARTIN_STATION_CODE", "17000")
os.environ.setdefault(
    "DELAY_ALERT_SNS_TOPIC_ARN",
    f"arn:aws:sns:{os.environ['AWS_DEFAULT_REGION']}:123456789012:test-zamora-delay-tweet",
)
os.environ.setdefault("DELAY_ALERT_THRESHOLD_MINUTES", "15")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

AWS_REGION = os.environ["AWS_DEFAULT_REGION"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_STATE_TABLE"]
S3_BUCKET_NAME = os.environ["DATALAKE_S3_BUCKET"]
ZAMORA_CODE = os.environ["ZAMORA_STATION_CODE"]
CHAMARTIN_CODE = os.environ["CHAMARTIN_STATION_CODE"]
DELAY_ALERT_SNS_TOPIC_ARN = os.environ["DELAY_ALERT_SNS_TOPIC_ARN"]
DELAY_ALERT_THRESHOLD_MINUTES = int(os.environ["DELAY_ALERT_THRESHOLD_MINUTES"])
