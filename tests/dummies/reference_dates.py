"""Fechas de referencia con día de la semana conocido, para tests deterministas."""
from datetime import date

# Lunes → tipo_dia "laborable"
MONDAY = date(2026, 1, 5)
# Sábado → tipo_dia "sabado"
SATURDAY = date(2026, 1, 3)
# Domingo → tipo_dia "domingo"
SUNDAY = date(2026, 1, 4)

assert MONDAY.weekday() == 0
assert SATURDAY.weekday() == 5
assert SUNDAY.weekday() == 6
