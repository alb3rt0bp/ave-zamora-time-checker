"""
trend_fetcher_env.py
Prepara el entorno para importar lambdas/trend_fetcher fuera del runtime
real de Lambda. train_tracker y trend_fetcher definen cada uno su propio
handler.py, así que este módulo importa el de trend_fetcher bajo un nombre
propio (trend_fetcher_handler) en vez de "handler" — evita pisar el
"handler" ya cacheado en sys.modules por tests/dummies/aws_env.py cuando la
suite completa se ejecuta en un único proceso (mismo problema ya resuelto
por tweet_notifier_env.py).
"""
import importlib.util
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TREND_FETCHER_DIR = os.path.join(REPO_ROOT, "lambdas", "trend_fetcher")

# append, no insert(0): igual que tweet_notifier_env.py, así "handler" (si
# alguna vez se importara sin cualificar) sigue resolviendo al de
# train_tracker si ya está en sys.path.
if TREND_FETCHER_DIR not in sys.path:
    sys.path.append(TREND_FETCHER_DIR)

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-south-2")

# Variables de entorno que handler.py/xfetch_client.py leen a nivel de
# módulo (import time). Se usa un nombre de secret simple (no un ARN
# completo): moto acepta el nombre como SecretId igual que la API real.
os.environ.setdefault("DATALAKE_S3_BUCKET", "test-zamora-datalake")
os.environ.setdefault("TRENDS_S3_KEY", "trends/latest_hashtags.json")
os.environ.setdefault("XFETCH_API_KEY_SECRET_ARN", "test-zamora-xfetch-api-key")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

AWS_REGION = os.environ["AWS_DEFAULT_REGION"]
DATALAKE_S3_BUCKET = os.environ["DATALAKE_S3_BUCKET"]
TRENDS_S3_KEY = os.environ["TRENDS_S3_KEY"]
XFETCH_API_KEY_SECRET_ARN = os.environ["XFETCH_API_KEY_SECRET_ARN"]


def import_trend_fetcher_handler():
    """Importa (una sola vez por proceso) lambdas/trend_fetcher/handler.py como "trend_fetcher_handler"."""
    if "trend_fetcher_handler" in sys.modules:
        return sys.modules["trend_fetcher_handler"]

    spec = importlib.util.spec_from_file_location(
        "trend_fetcher_handler", os.path.join(TREND_FETCHER_DIR, "handler.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["trend_fetcher_handler"] = module
    spec.loader.exec_module(module)
    return module
