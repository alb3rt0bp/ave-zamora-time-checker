"""Helpers de fecha/hora compartidos por los tests."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")


def madrid_time_to_utc(day: date, hour: int, minute: int) -> datetime:
    """Convierte una hora local de Madrid, en el día dado, a datetime UTC."""
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=MADRID_TZ)
    return local.astimezone(timezone.utc)
