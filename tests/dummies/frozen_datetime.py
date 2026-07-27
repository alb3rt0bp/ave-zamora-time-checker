"""
frozen_datetime.py
Permite fijar el valor que devuelve datetime.now() dentro de handler.py sin
depender de librerías externas (freezegun, time-machine...): se construye una
subclase de datetime cuyo classmethod now() siempre devuelve el instante fijado,
y se sustituye `handler.datetime` por ella con unittest.mock.patch.
"""
from datetime import datetime as _real_datetime


def make_frozen_datetime(fixed_utc_now: _real_datetime):
    """fixed_utc_now debe ser un datetime con tzinfo=timezone.utc."""

    class FrozenDateTime(_real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_utc_now
            return fixed_utc_now.astimezone(tz)

    return FrozenDateTime
