#!/usr/bin/env python3
"""
export_gtfs_schedule_reference.py
Descarga el GTFS estático de Renfe y exporta a CSV el resultado exacto de
lambdas/api/gtfs_schedule_reference.build_schedule_reference — el mismo
horario de referencia que sirve /trains/schedule en producción (patrón
semanal real, derivado de calendar.txt + calendar_dates.txt; ver el
docstring de ese módulo) — sin ninguna lógica de comparación añadida, para
poder revisar a ojo qué está devolviendo realmente esa función tal cual.

Uso:
    python3 scripts/export_gtfs_schedule_reference.py
    python3 scripts/export_gtfs_schedule_reference.py --date 2026-10-16 --csv reference_2026-10-16.csv
"""

import argparse
import csv
import ssl
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lambdas" / "train_tracker"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lambdas" / "api"))

try:
    # Algunas instalaciones de python.org en macOS no traen el almacén de
    # certificados raíz del sistema (falla con CERTIFICATE_VERIFY_FAILED al
    # descargar el GTFS por HTTPS). Si `certifi` está disponible, se usa como
    # almacén de confianza para este script en lugar de requerir que quien lo
    # ejecute configure SSL_CERT_FILE a mano.
    import certifi
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
except ImportError:
    pass

from gtfs_client import GtfsClient  # noqa: E402
from gtfs_schedule_reference import build_schedule_reference  # noqa: E402

ZAMORA_CODE = "30200"
CHAMARTIN_CODE = "17000"

_WEEKDAY_NAMES = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

CSV_FIELDS = ["cod_comercial", "sentido", "hora_salida", "hora_llegada_destino", "weekdays"]


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _weekdays_str(weekdays: list[int]) -> str:
    return ",".join(_WEEKDAY_NAMES[d] for d in weekdays)


def write_csv(trains: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for train in trains:
            writer.writerow({
                "cod_comercial": train["cod_comercial"],
                "sentido": train["sentido"],
                "hora_salida": train["hora_salida"],
                "hora_llegada_destino": train["hora_llegada_destino"],
                "weekdays": _weekdays_str(train["weekdays"]),
            })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=date.today().isoformat(),
                         help="Fecha de referencia (YYYY-MM-DD) contra la que resolver calendar.txt, por defecto hoy")
    parser.add_argument("--zamora-code", default=ZAMORA_CODE)
    parser.add_argument("--chamartin-code", default=CHAMARTIN_CODE)
    parser.add_argument("--csv", default="gtfs_schedule_reference.csv",
                         help="Ruta del CSV de salida (por defecto gtfs_schedule_reference.csv)")
    args = parser.parse_args()

    reference_date = _parse_date(args.date)
    log_extra = {"script": "export_gtfs_schedule_reference"}

    print("Descargando GTFS estático de Renfe...")
    gtfs_files = GtfsClient(log_extra).download_and_extract()

    print(f"Resolviendo horario de referencia para {reference_date.isoformat()}...")
    trains = build_schedule_reference(gtfs_files, reference_date, args.zamora_code, args.chamartin_code, log_extra)

    csv_path = Path(args.csv)
    write_csv(trains, csv_path)
    print(f"CSV escrito en {csv_path.resolve()} ({len(trains)} trenes).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
