"""
tweet_notifier_env.py
Prepara el entorno para importar lambdas/tweet_notifier fuera del runtime
real de Lambda. train_tracker y tweet_notifier definen cada uno su propio
handler.py, así que este módulo importa el de tweet_notifier bajo un nombre
propio (tweet_notifier_handler) en vez de "handler" — evita pisar el
"handler" ya cacheado en sys.modules por tests/dummies/aws_env.py cuando la
suite completa se ejecuta en un único proceso.

x_client.py no colisiona con nada de train_tracker, así que se importa de
forma normal una vez lambdas/tweet_notifier está en sys.path.
"""
import importlib.util
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TWEET_NOTIFIER_DIR = os.path.join(REPO_ROOT, "lambdas", "tweet_notifier")

# append, no insert(0): así "handler" (si alguna vez se importara sin
# cualificar) sigue resolviendo al de train_tracker si ya está en sys.path.
if TWEET_NOTIFIER_DIR not in sys.path:
    sys.path.append(TWEET_NOTIFIER_DIR)

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-south-2")

# Variable de entorno que handler.py lee a nivel de módulo (import time).
# Se usa un nombre de secret simple (no un ARN completo): moto acepta el
# nombre como SecretId igual que la API real.
os.environ.setdefault("X_API_CREDENTIALS_SECRET_ARN", "test-zamora-x-api-credentials")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

AWS_REGION = os.environ["AWS_DEFAULT_REGION"]
X_API_CREDENTIALS_SECRET_ARN = os.environ["X_API_CREDENTIALS_SECRET_ARN"]


def import_tweet_notifier_handler():
    """Importa (una sola vez por proceso) lambdas/tweet_notifier/handler.py como "tweet_notifier_handler"."""
    if "tweet_notifier_handler" in sys.modules:
        return sys.modules["tweet_notifier_handler"]

    spec = importlib.util.spec_from_file_location(
        "tweet_notifier_handler", os.path.join(TWEET_NOTIFIER_DIR, "handler.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["tweet_notifier_handler"] = module
    spec.loader.exec_module(module)
    return module
