"""
metrics_writer.py
Actualiza la tabla DynamoDB de métricas precalculadas (por tren / semanal /
mensual / global) a partir de los registros que daily_dump_handler acaba de
volcar a S3, agregándolos mediante lectura-modificación-escritura en Python
plano (no UpdateItem con ADD anidado: paths como por_tren.{cod}.total_viajes
exigirían que el mapa padre ya existiese, complejidad innecesaria a este
volumen de escritura — un puñado de pares GetItem/PutItem una vez al día,
sin concurrencia).

Los registros 'cancelado' se excluyen enteramente (ni cuentan en el
denominador), igual que ya hace el resto del sistema para no contaminar
medias con retrasos inexistentes.

Cada viaje se clasifica en uno de 4 tramos mutuamente excluyentes (usados
para el gráfico de tipo queso del frontend): 'puntual' (<5min), 'leve'
(5min..threshold_minutes), 'significativo' (threshold_minutes..60min) y
'grave' (>60min). threshold_minutes es SIGNIFICANT_DELAY_THRESHOLD_MINUTES,
un umbral configurable deliberadamente independiente de
DELAY_ALERT_THRESHOLD_MINUTES (ese controla los tuits automáticos, un
concern distinto que hoy comparte el mismo valor por coincidencia). Los
tramos se nombran por severidad, no por el número literal, precisamente
porque el límite intermedio (leve/significativo) es configurable. "Retraso
significativo" a efectos de ranking/riesgo = tramos significativo+grave.

Cada item guarda last_aggregated_date: si ya coincide con el día que se está
volcando, se salta sin sumar de nuevo — necesario porque EventBridge
Scheduler invoca daily_dump_handler de forma asíncrona y puede reintentar
tras un fallo, y sin esta guarda un reintento duplicaría el día.
"""

import logging
import os
from datetime import date, datetime

logger = logging.getLogger(f"train_tracker.{__name__}")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Contadores de nivel superior de TRAIN#/WEEK#/MONTH#/GLOBAL: los 4 tramos
# de retraso, usados para el gráfico de tipo queso.
_ZERO_DELAY_BUCKETS = {
    "total_viajes": 0,
    "viajes_bucket_puntual": 0,
    "viajes_bucket_leve": 0,
    "viajes_bucket_significativo": 0,
    "viajes_bucket_grave": 0,
    "suma_retraso_significativo_minutos": 0,
}

# Contadores de los desgloses anidados (por_tren/por_dia_semana en WEEK#/
# MONTH#, y por_dia_semana/por_franja_horaria en GLOBAL): un único contador
# binario "significativo o no", suficiente para rankear sin necesitar el
# detalle de 4 tramos a ese nivel.
_ZERO_SIGNIFICANT_BUCKET = {
    "total_viajes": 0,
    "viajes_retraso_significativo": 0,
    "suma_retraso_significativo_minutos": 0,
}


def _bucket_for(minutos_retraso: int, threshold_minutes: int) -> str:
    if minutos_retraso < 5:
        return "puntual"
    if minutos_retraso <= threshold_minutes:
        return "leve"
    if minutos_retraso <= 60:
        return "significativo"
    return "grave"


def _franja_for(hora_paso_zamora: str | None) -> str | None:
    """
    Banda horaria a partir de la hora ('HH:MM') de paso por Zamora, el único
    campo de hora consistentemente presente para ambos sentidos. 'noche' es
    el tramo por defecto (>=20:00 o <06:00): cubre tanto la banda 20-24
    especificada como una llegada con retraso que empuje la hora más allá de
    medianoche, algo que no debería ocurrir en operación normal (el polling
    solo corre 07:00-23:59) pero que la aritmética hora_programada+retraso
    podría producir igualmente. Devuelve None si no hay hora que asignar
    (ver MetricsWriter._update_global_item).
    """
    if not hora_paso_zamora:
        return None
    hour = int(hora_paso_zamora.split(":")[0])
    if 6 <= hour < 14:
        return "manana"
    if 14 <= hour < 20:
        return "tarde"
    return "noche"


class MetricsWriter:
    def __init__(self, table, threshold_minutes: int, log_extra: dict):
        self.table = table
        self.threshold_minutes = threshold_minutes
        self.log_extra = log_extra

    def update_daily_metrics(self, records: list[dict], target_date: date, now_local: datetime) -> None:
        """Agrega los registros (ya no cancelados) del día en los items TRAIN#/WEEK#/MONTH#/GLOBAL."""
        active = [r for r in records if not r.get("cancelado")]
        if not active:
            logger.info(
                "Sin trenes activos para %s; no se actualizan métricas.",
                target_date.isoformat(), extra=self.log_extra
            )
            return

        target_iso = target_date.isoformat()
        weekday = target_date.weekday()  # 0=lunes .. 6=domingo
        iso_year, iso_week, _ = target_date.isocalendar()

        self._update_train_items(active, target_iso, now_local)
        self._update_period_item(
            pk=f"WEEK#{iso_year}-W{iso_week:02d}",
            extra_keys={
                "iso_year": iso_year,
                "iso_week": iso_week,
                "week_start": date.fromisocalendar(iso_year, iso_week, 1).isoformat(),
                "week_end": date.fromisocalendar(iso_year, iso_week, 7).isoformat(),
            },
            active=active, weekday=weekday, target_iso=target_iso, now_local=now_local,
        )
        self._update_period_item(
            pk=f"MONTH#{target_date.year}-{target_date.month:02d}",
            extra_keys={"year": target_date.year, "month": target_date.month},
            active=active, weekday=weekday, target_iso=target_iso, now_local=now_local,
        )
        self._update_global_item(active, weekday, target_iso, now_local)

        logger.info(
            "Métricas actualizadas para %s (%d trenes activos)",
            target_iso, len(active), extra=self.log_extra
        )

    def _update_train_items(self, active: list[dict], target_iso: str, now_local: datetime) -> None:
        for cod, recs in self._group_by_train(active).items():
            pk = f"TRAIN#{cod}"
            item = self.table.get_item(Key={"pk": pk}).get("Item")
            if item is None:
                item = {"pk": pk, "cod_comercial": cod, "sentido": recs[0]["sentido"], **_ZERO_DELAY_BUCKETS}

            if item.get("last_aggregated_date") == target_iso:
                continue  # ya agregado (reintento de daily_dump_handler)

            contribution = self._aggregate_buckets(recs)
            for key in _ZERO_DELAY_BUCKETS:
                item[key] = int(item.get(key, 0)) + contribution[key]
            item["last_aggregated_date"] = target_iso
            item["updated_at"] = now_local.isoformat()

            self.table.put_item(Item=item)

    def _update_period_item(self, pk: str, extra_keys: dict, active: list[dict], weekday: int,
                             target_iso: str, now_local: datetime) -> None:
        item = self.table.get_item(Key={"pk": pk}).get("Item")
        if item is None:
            item = {"pk": pk, **extra_keys, **_ZERO_DELAY_BUCKETS, "por_tren": {}, "por_dia_semana": {}}

        if item.get("last_aggregated_date") == target_iso:
            return  # ya agregado (reintento de daily_dump_handler)

        overall = self._aggregate_buckets(active)
        for key in _ZERO_DELAY_BUCKETS:
            item[key] = int(item.get(key, 0)) + overall[key]

        por_tren = dict(item.get("por_tren") or {})
        for cod, recs in self._group_by_train(active).items():
            por_tren[cod] = self._sum_significant(
                por_tren.get(cod, _ZERO_SIGNIFICANT_BUCKET), self._aggregate_significant(recs)
            )
        item["por_tren"] = por_tren

        por_dia_semana = dict(item.get("por_dia_semana") or {})
        day_key = str(weekday)
        por_dia_semana[day_key] = self._sum_significant(
            por_dia_semana.get(day_key, _ZERO_SIGNIFICANT_BUCKET), self._aggregate_significant(active)
        )
        item["por_dia_semana"] = por_dia_semana

        item["last_aggregated_date"] = target_iso
        item["updated_at"] = now_local.isoformat()

        self.table.put_item(Item=item)

    def _update_global_item(self, active: list[dict], weekday: int, target_iso: str, now_local: datetime) -> None:
        pk = "GLOBAL"
        item = self.table.get_item(Key={"pk": pk}).get("Item")
        if item is None:
            item = {
                "pk": pk, **_ZERO_DELAY_BUCKETS,
                "por_dia_semana": {}, "por_franja_horaria": {},
                "first_aggregated_date": target_iso,
            }

        if item.get("last_aggregated_date") == target_iso:
            return  # ya agregado (reintento de daily_dump_handler)

        # No basta con fijarla solo al crear el item: si el pipeline en vivo
        # ya lo creó (p. ej. con la fecha de ayer) y luego se ejecuta un
        # backfill hacia atrás (scripts/backfill_metrics.py, en cualquier
        # orden), first_aggregated_date debe seguir siendo la fecha más
        # antigua vista hasta ahora, no solo "la primera vez que este item
        # se creó". Las fechas ISO ordenan correctamente como string.
        item["first_aggregated_date"] = min(item.get("first_aggregated_date", target_iso), target_iso)

        overall = self._aggregate_buckets(active)
        for key in _ZERO_DELAY_BUCKETS:
            item[key] = int(item.get(key, 0)) + overall[key]

        por_dia_semana = dict(item.get("por_dia_semana") or {})
        day_key = str(weekday)
        por_dia_semana[day_key] = self._sum_significant(
            por_dia_semana.get(day_key, _ZERO_SIGNIFICANT_BUCKET), self._aggregate_significant(active)
        )
        item["por_dia_semana"] = por_dia_semana

        by_franja: dict[str, list[dict]] = {}
        for record in active:
            franja = _franja_for(record.get("hora_paso_zamora"))
            if franja is not None:
                by_franja.setdefault(franja, []).append(record)

        por_franja_horaria = dict(item.get("por_franja_horaria") or {})
        for franja, recs in by_franja.items():
            por_franja_horaria[franja] = self._sum_significant(
                por_franja_horaria.get(franja, _ZERO_SIGNIFICANT_BUCKET), self._aggregate_significant(recs)
            )
        item["por_franja_horaria"] = por_franja_horaria

        item["last_aggregated_date"] = target_iso
        item["updated_at"] = now_local.isoformat()

        self.table.put_item(Item=item)

    def _aggregate_buckets(self, records: list[dict]) -> dict:
        counts = dict(_ZERO_DELAY_BUCKETS)
        counts["total_viajes"] = len(records)
        for record in records:
            minutos = record["minutos_retraso"]
            bucket = _bucket_for(minutos, self.threshold_minutes)
            counts[f"viajes_bucket_{bucket}"] += 1
            if bucket in ("significativo", "grave"):
                counts["suma_retraso_significativo_minutos"] += minutos
        return counts

    def _aggregate_significant(self, records: list[dict]) -> dict:
        significativos = [r for r in records if r["minutos_retraso"] > self.threshold_minutes]
        return {
            "total_viajes": len(records),
            "viajes_retraso_significativo": len(significativos),
            "suma_retraso_significativo_minutos": sum(r["minutos_retraso"] for r in significativos),
        }

    @staticmethod
    def _group_by_train(records: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for record in records:
            grouped.setdefault(record["cod_comercial"], []).append(record)
        return grouped

    @staticmethod
    def _sum_significant(a: dict, b: dict) -> dict:
        return {key: int(a.get(key, 0)) + int(b.get(key, 0)) for key in _ZERO_SIGNIFICANT_BUCKET}
