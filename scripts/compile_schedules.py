#!/usr/bin/env python3
"""
compile_schedules.py
Convierte los 6 CSV de horarios Zamora → config/train_schedules.json
Uso: python3 scripts/compile_schedules.py

El JSON resultante es la fuente de verdad para la Lambda y para
generar las reglas de EventBridge Scheduler.
"""

import csv
import json
import os
import re
from pathlib import Path

# ── Mapeo de nombres de fichero a tipo de día y sentido ──────────────────────
FILE_MAP = {
    "trenes_ida_madrid_laborable.csv":  {"tipo_dia": "laborable", "sentido": "Madrid"},
    "trenes_ida_madrid_sabado.csv":     {"tipo_dia": "sabado",    "sentido": "Madrid"},
    "trenes_ida_madrid_domingo.csv":    {"tipo_dia": "domingo",   "sentido": "Madrid"},
    "trenes_vuelta_madrid_laborable.csv": {"tipo_dia": "laborable", "sentido": "Galicia"},
    "trenes_vuelta_madrid_sabado.csv":    {"tipo_dia": "sabado",    "sentido": "Galicia"},
    "trenes_vuelta_madrid_domingo.csv":   {"tipo_dia": "domingo",   "sentido": "Galicia"},
}

# ── Días de la semana que corresponden a cada tipo ───────────────────────────
TIPO_DIA_WEEKDAYS = {
    "laborable": [0, 1, 2, 3, 4],   # Lunes–Viernes (isoweekday 1-5)
    "sabado":    [5],                # Sábado
    "domingo":   [6],                # Domingo
}


def parse_hour(raw: str) -> str:
    """Normaliza '07.41' o '7:41' a 'HH:MM'."""
    raw = raw.strip()
    raw = raw.replace(".", ":")
    parts = raw.split(":")
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def load_csv(filepath: str) -> list[dict]:
    """Lee un CSV con separador ';' y devuelve lista de dicts normalizados."""
    rows = []
    with open(filepath, newline="", encoding="utf-8") as fh:
        # El CSV tiene una única columna cuyo nombre incluye todos los campos
        # separados por ';' — pandas lo leería igual, pero aquí usamos csv puro.
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            # Limpiar espacios en claves y valores
            row = {k.strip(): v.strip() for k, v in row.items()}

            # La primera columna puede llamarse 'Tren / Recorrido' o variantes
            cod_key = next(
                (k for k in row if "tren" in k.lower() or "recorrido" in k.lower()),
                None,
            )
            if cod_key is None:
                continue

            cod = row[cod_key].strip()
            # A veces el código viene con espacios o ceros extra
            cod = re.sub(r"\s+", "", cod)

            rows.append({
                "cod_comercial": cod,
                "hora_salida": parse_hour(row.get("Salida", "00:00")),
                "hora_llegada_destino": parse_hour(row.get("Llegada", "00:00")),
                "duracion_raw": row.get("Duración", "").strip(),
            })
    return rows


def build_schedules(data_dir: str) -> dict:
    """
    Construye el diccionario maestro de horarios.

    Estructura de salida:
    {
      "version": "1.0",
      "generated_at": "<ISO timestamp>",
      "trains": [
        {
          "cod_comercial": "04154",
          "sentido": "Madrid",
          "tipo_dia": "laborable",
          "weekdays": [0,1,2,3,4],
          "hora_salida": "07:41",
          "hora_llegada_destino": "08:56"
        },
        ...
      ]
    }
    """
    from datetime import datetime, timezone

    trains = []

    for filename, meta in FILE_MAP.items():
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            print(f"  ⚠ No encontrado: {filepath}")
            continue

        rows = load_csv(filepath)
        print(f"  ✓ {filename}: {len(rows)} trenes")

        for r in rows:
            trains.append({
                "cod_comercial": r["cod_comercial"],
                "sentido": meta["sentido"],
                "tipo_dia": meta["tipo_dia"],
                "weekdays": TIPO_DIA_WEEKDAYS[meta["tipo_dia"]],
                "hora_salida": r["hora_salida"],
                "hora_llegada_destino": r["hora_llegada_destino"],
                "duracion_raw": r["duracion_raw"],
            })

    # Ordenar para que el JSON sea determinista
    trains.sort(key=lambda t: (t["sentido"], t["tipo_dia"], t["hora_salida"]))

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "zamora_station_code": "71801",
        "polling_window_minutes": 30,
        "trains": trains,
    }


def main():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"   # pasa los CSVs aquí antes de ejecutar
    output_path = project_root / "config" / "train_schedules.json"

    print("=== Compilando horarios de trenes Zamora ===")

    schedules = build_schedules(str(data_dir))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(schedules, fh, ensure_ascii=False, indent=2)

    print(f"\n✅ Guardado en {output_path}")
    print(f"   Total entradas: {len(schedules['trains'])}")

    # Resumen por tipo
    from collections import Counter
    counter = Counter((t["sentido"], t["tipo_dia"]) for t in schedules["trains"])
    for (sentido, tipo), count in sorted(counter.items()):
        print(f"   {sentido:8s} / {tipo:10s}: {count} trenes")


if __name__ == "__main__":
    main()
