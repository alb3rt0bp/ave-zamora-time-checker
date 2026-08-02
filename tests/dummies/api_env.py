"""
api_env.py
Prepara el entorno para importar lambdas/api fuera del runtime real de
Lambda. train_tracker, tweet_notifier y api definen cada uno su propio
handler.py, así que este módulo importa el de api bajo un nombre propio
(api_handler) en vez de "handler" — evita pisar el "handler" ya cacheado en
sys.modules por tests/dummies/aws_env.py cuando la suite completa se ejecuta
en un único proceso (mismo problema ya resuelto por tweet_notifier_env.py).

Reutiliza los nombres de tabla/bucket de test ya definidos en aws_env.py
(DYNAMODB_TABLE_NAME, S3_BUCKET_NAME) en vez de redefinir nuevas constantes,
para que los tests de api y de train_tracker apunten a los mismos recursos
moto.
"""
import importlib.util
import os
import sys

from tests.dummies import aws_env  # noqa: F401 - fuerza credenciales/env compartidos

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(REPO_ROOT, "lambdas", "api")

# append, no insert(0): igual que tweet_notifier_env.py, así "handler" (si
# alguna vez se importara sin cualificar) sigue resolviendo al de
# train_tracker si ya está en sys.path.
if API_DIR not in sys.path:
    sys.path.append(API_DIR)

# Variables de entorno que lambdas/api/handler.py lee a nivel de módulo.
os.environ.setdefault("DATALAKE_S3_BUCKET", aws_env.S3_BUCKET_NAME)
os.environ.setdefault("DYNAMODB_STATE_TABLE", aws_env.DYNAMODB_TABLE_NAME)
os.environ.setdefault("LOG_LEVEL", "DEBUG")

AWS_REGION = aws_env.AWS_REGION
DYNAMODB_TABLE_NAME = aws_env.DYNAMODB_TABLE_NAME
S3_BUCKET_NAME = aws_env.S3_BUCKET_NAME


def import_api_handler():
    """Importa (una sola vez por proceso) lambdas/api/handler.py como "api_handler"."""
    if "api_handler" in sys.modules:
        return sys.modules["api_handler"]

    spec = importlib.util.spec_from_file_location(
        "api_handler", os.path.join(API_DIR, "handler.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["api_handler"] = module
    spec.loader.exec_module(module)
    return module
