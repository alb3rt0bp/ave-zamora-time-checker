"""
schedule_resolver.py
Punto de entrada único para obtener el horario de trenes de HOY: intenta la
caché en S3 (schedule_cache.py); si no existe, descarga y resuelve desde
GTFS (gtfs_client.py + gtfs_schedule_builder.py) y la cachea; si cualquiera
de esos pasos falla, cae al fichero estático embebido
(config/train_schedules.json, filtrado por tipo de día) y avisa por email
para revisión manual.

A diferencia de los enriquecimientos aditivos de este proyecto (GTFS-RT,
tendencias de X — que degradan en silencio porque son opcionales), este
horario decide QUÉ trenes se monitorizan cada día: un fallo aquí no puede
pasar desapercibido, de ahí el aviso explícito en vez de solo un log.

Tanto _seed_todays_trains como ScheduleMatcher (ver handler.py) consumen el
resultado de resolve_todays_schedule, para que el sembrado en DynamoDB y las
ventanas de polling de todo el día estén siempre de acuerdo sobre qué
horario rige hoy.
"""

import logging
import os
from datetime import date
from typing import Callable

from gtfs_client import GtfsClient
from gtfs_schedule_builder import build_todays_trains
import schedule_cache

logger = logging.getLogger(f"train_tracker.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

GTFS_SCHEDULE_ENABLED = os.environ.get("GTFS_SCHEDULE_ENABLED", "false").lower() == "true"


def resolve_todays_schedule(
    s3,
    bucket: str,
    target_date: date,
    zamora_code: str,
    chamartin_code: str,
    static_fallback: dict,
    alert_publisher: Callable[[str], None],
    log_extra: dict,
) -> dict:
    """
    Devuelve {"polling_window_minutes": int, "trains": [...]} con
    exactamente los trenes activos en target_date — filtrados, sea cual sea
    el origen (GTFS o fallback estático), para que ScheduleMatcher y
    _seed_todays_trains no necesiten saber de dónde vino el horario.

    static_fallback: contenido de config/train_schedules.json (todos los
    tipo_dia mezclados, tal cual lo carga handler.py a nivel de módulo).
    alert_publisher: callable(mensaje) invocado cuando hay que recurrir al
    fallback estático — desacoplado de SNS directamente para poder testear
    este módulo sin mocks de boto3.
    """
    if not GTFS_SCHEDULE_ENABLED:
        return _filtered_static_fallback(static_fallback, target_date)

    cached = schedule_cache.get_cached_schedule(s3, bucket, target_date, log_extra)
    if cached is not None:
        return _with_window(static_fallback, cached)

    try:
        gtfs_files = GtfsClient(log_extra).download_and_extract()
        trains = build_todays_trains(gtfs_files, target_date, zamora_code, chamartin_code, log_extra)
    except Exception as exc:
        logger.error(
            "Fallo resolviendo horario desde GTFS para %s: %s — usando fichero estático de reserva",
            target_date.isoformat(), exc, extra=log_extra,
        )
        alert_publisher(
            f"No se pudo resolver el horario de trenes desde GTFS para {target_date.isoformat()} "
            f"({exc}). Se ha usado el fichero estático de reserva (train_schedules.json), que puede "
            f"estar desactualizado respecto al horario real de Renfe. Revisar manualmente."
        )
        return _filtered_static_fallback(static_fallback, target_date)

    if not trains:
        logger.error(
            "GTFS resuelto para %s sin ningún tren — usando fichero estático de reserva "
            "(posible cambio de formato en el feed de Renfe)", target_date.isoformat(), extra=log_extra,
        )
        alert_publisher(
            f"El horario resuelto desde GTFS para {target_date.isoformat()} salió vacío (posible "
            f"cambio de formato en el feed de Renfe, o de los códigos de estación de Zamora/Chamartín). "
            f"Se ha usado el fichero estático de reserva. Revisar manualmente."
        )
        return _filtered_static_fallback(static_fallback, target_date)

    schedule_cache.put_cached_schedule(s3, bucket, target_date, trains, log_extra)
    return _with_window(static_fallback, trains)


def _with_window(static_fallback: dict, trains: list[dict]) -> dict:
    return {
        "polling_window_minutes": static_fallback.get("polling_window_minutes", 30),
        "trains": trains,
    }


def _filtered_static_fallback(static_fallback: dict, target_date: date) -> dict:
    tipo_dia = _tipo_dia_for(target_date)
    trains = [t for t in static_fallback.get("trains", []) if t.get("tipo_dia") == tipo_dia]
    return _with_window(static_fallback, trains)


def _tipo_dia_for(target_date: date) -> str:
    weekday = target_date.weekday()
    if weekday in (0, 1, 2, 3, 4):
        return "laborable"
    elif weekday == 5:
        return "sabado"
    else:
        return "domingo"
