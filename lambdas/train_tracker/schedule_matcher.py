"""
schedule_matcher.py
Determina qué trenes están dentro de la ventana de monitorización activa
en el momento de la ejecución de la Lambda.

Ventana según sentido:
  - Madrid:  desde (hora_salida - 1h) hasta (hora_llegada_destino +
             último retraso conocido en DynamoDB + 10 min). Si aún no hay
             estado en DynamoDB, se asume retraso 0.
  - Galicia: desde (hora_salida - 1h) sin límite superior; se deja de
             considerar activo cuando el estado en DynamoDB queda 'done'
             (capturado en Zamora).
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger(__name__)


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

    def get_active_trains(
        self,
        now: datetime,
        state_lookup: Optional[Callable[[str], Optional[dict]]] = None,
    ) -> list[dict]:
        """
        Devuelve los trenes cuya ventana de monitorización incluye `now`.

        `now` debe ser un datetime con timezone (hora local española).
        `state_lookup(cod_comercial)` devuelve el último estado conocido en
        DynamoDB para ese tren hoy (o None si no existe); se usa para conocer
        el retraso acumulado y calcular con precisión el cierre de ventana de
        los trenes con sentido Madrid.
        """
        weekday = now.weekday()  # 0=Lunes … 6=Domingo
        tipo_dia = self._weekday_to_tipo(weekday)

        active = []
        for train in self.trains:
            # Verificar que el tipo de día coincide
            if train["tipo_dia"] != tipo_dia:
                continue
            # Verificar ventana temporal
            if self._is_active(train, now, state_lookup):
                active.append(train)

        return active

    def _weekday_to_tipo(self, weekday: int) -> str:
        if weekday in (0, 1, 2, 3, 4):
            return "laborable"
        elif weekday == 5:
            return "sabado"
        else:
            return "domingo"

    def _is_active(
        self,
        train: dict,
        now: datetime,
        state_lookup: Optional[Callable[[str], Optional[dict]]],
    ) -> bool:
        """
        Ventana activa desde (hora_salida - 1h). El cierre depende del sentido:
          - Madrid:  hora_llegada_destino + último retraso conocido + 10 min.
          - Galicia: sin cierre por tiempo (lo detiene el estado 'done').
        """
        h, m = map(int, train["hora_salida"].split(":"))
        salida = now.replace(hour=h, minute=m, second=0, microsecond=0)
        window_start = salida - timedelta(hours=1)

        if now < window_start:
            return False

        if train["sentido"] != "Madrid":
            return True

        hh, mm = map(int, train["hora_llegada_destino"].split(":"))
        llegada_programada = now.replace(hour=hh, minute=mm, second=0, microsecond=0)

        ult_retraso = 0
        if state_lookup is not None:
            state = state_lookup(train["cod_comercial"])
            if state:
                ult_retraso = int(state.get("ult_retraso", 0) or 0)

        window_end = llegada_programada + timedelta(minutes=ult_retraso + 10)
        return now <= window_end

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
