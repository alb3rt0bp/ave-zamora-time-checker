"""
schedule_matcher.py
Determina qué trenes están dentro de la ventana de monitorización activa
en el momento de la ejecución de la Lambda.

Ventana: desde (hora_programada - window_min) hasta (hora_programada + window_min + max_delay_buffer)
donde max_delay_buffer = 60 min (cubre retrasos habituales de Renfe)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Buffer adicional para retrasos grandes (minutos)
MAX_DELAY_BUFFER_MINUTES = 60


class ScheduleMatcher:
    def __init__(self, config: dict):
        """
        config: contenido de train_schedules.json
        {
          "polling_window_minutes": 30,
          "trains": [
            {
              "cod_comercial": "04154",
              "sentido": "Madrid",
              "tipo_dia": "laborable",
              "weekdays": [0,1,2,3,4],
              "hora_salida": "07:41",
              ...
            }
          ]
        }
        """
        self.trains: list[dict] = config["trains"]
        self.window_minutes: int = config.get("polling_window_minutes", 30)

    def get_active_trains(self, now: datetime) -> list[dict]:
        """
        Devuelve los trenes cuya ventana de monitorización incluye `now`.

        `now` debe ser un datetime con timezone (hora local española).
        """
        weekday = now.weekday()  # 0=Lunes … 6=Domingo
        tipo_dia = self._weekday_to_tipo(weekday)

        active = []
        for train in self.trains:
            # Verificar que el tipo de día coincide
            if train["tipo_dia"] != tipo_dia:
                continue
            # Verificar ventana temporal
            if self._in_window(train["hora_salida"], now):
                active.append(train)

        return active

    def _weekday_to_tipo(self, weekday: int) -> str:
        if weekday in (0, 1, 2, 3, 4):
            return "laborable"
        elif weekday == 5:
            return "sabado"
        else:
            return "domingo"

    def _in_window(self, hora_paso: str, now: datetime) -> bool:
        """
        Devuelve True si `now` está en el intervalo:
          [hora_paso - window_min,  hora_paso + window_min + MAX_DELAY_BUFFER]
        """
        h, m = map(int, hora_paso.split(":"))
        scheduled = now.replace(hour=h, minute=m, second=0, microsecond=0)

        window_start = scheduled - timedelta(minutes=self.window_minutes)
        window_end   = scheduled + timedelta(minutes=self.window_minutes + MAX_DELAY_BUFFER_MINUTES)

        return window_start <= now <= window_end

    def get_trains_for_day_type(self, tipo_dia: str) -> list[dict]:
        """Filtra trenes por tipo de día (útil para tests y scripts)."""
        return [t for t in self.trains if t["tipo_dia"] == tipo_dia]

    def get_eventbridge_schedules(self, timezone_id: str = "Europe/Madrid") -> list[dict]:
        """
        Genera las definiciones de reglas EventBridge Scheduler para todos los trenes.
        Cada regla se activa 30 min antes de la hora programada de paso.

        Útil para el script de despliegue / CloudFormation.
        """
        seen = set()
        rules = []

        for train in self.trains:
            h, m = map(int, train["hora_salida"].split(":"))
            # Activar la ventana 30 min antes
            start_h, start_m = self._subtract_minutes(h, m, self.window_minutes)
            cron_expr = self._weekdays_to_cron(train["weekdays"], start_h, start_m)

            rule_id = f"{train['cod_comercial']}-{train['tipo_dia']}"
            if rule_id in seen:
                continue
            seen.add(rule_id)

            rules.append({
                "name": f"zamora-train-{rule_id}",
                "schedule_expression": cron_expr,
                "timezone": timezone_id,
                "train": train,
            })

        return rules

    @staticmethod
    def _subtract_minutes(h: int, m: int, delta: int) -> tuple[int, int]:
        total = h * 60 + m - delta
        if total < 0:
            total += 24 * 60
        return divmod(total, 60)

    @staticmethod
    def _weekdays_to_cron(weekdays: list[int], h: int, m: int) -> str:
        """
        Convierte lista de weekdays (0=lun) a expresión cron de EventBridge.
        EventBridge usa: cron(min hour dom month dow year)
        dow: 1=dom, 2=lun … 7=sab (1-7, al contrario que Python)
        """
        # Python weekday 0=lun → EventBridge dow 2=lun
        eb_map = {0: 2, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 1}
        eb_days = sorted(eb_map[d] for d in weekdays)
        dow_str = ",".join(map(str, eb_days))
        return f"cron({m} {h} ? * {dow_str} *)"
