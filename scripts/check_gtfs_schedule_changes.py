#!/usr/bin/env python3
"""
check_gtfs_schedule_changes.py
Descarga el GTFS estático de Renfe UNA vez y compara, para cada tren que
pasa por Zamora, el patrón semanal real resuelto por
lambdas/api/gtfs_schedule_reference.build_schedule_reference en una fecha
"antes" contra el resuelto en una fecha "después" — para detectar si Renfe
ya ha publicado en su GTFS el cambio de horarios anunciado para mediados de
octubre de 2026.

Por qué build_schedule_reference y no comparar fechas concretas una a una
--------------------------------------------------------------------------
Una primera versión de este script comparaba fechas concretas (p. ej. un
miércoles de esta semana contra un miércoles de la semana del 16 de
octubre) usando gtfs_schedule_builder.build_todays_trains. Eso resultó
frágil: en el feed real de Renfe, `service_id` es en la práctica un
intervalo de validez de ~3-4 semanas (p. ej.
"2026-09-232026-10-14045051" = vigente 2026-09-23..10-14), y Renfe reemite
un intervalo nuevo para el mismo tren cada pocas semanas manteniendo el
mismo patrón — así que una comparación de fechas puntuales cerca de esa
frontera de intervalo (que resultó caer justo hacia el 14-15 de octubre)
producía altas/bajas que eran solo ruido de la frontera, no un cambio de
horario real (ver la investigación que motivó este fix: 04505 resultó
circular los domingos en los tres intervalos consecutivos comprobados a
mano, sin ningún cambio real).

build_schedule_reference ya resuelve esto correctamente (tras su propio
fix, ver su docstring): para una fecha de referencia, expande el intervalo
completo del service_id vigente ese día aplicando calendar_dates.txt, y
devuelve el conjunto real de weekdays en los que circula cada tren. Comparar
dos llamadas a esa función (una con --before, otra con --after) compara
patrones semanales completos en vez de muestras de fechas sueltas.

Trenes agrupados por tipo de día (laborable/sábado/domingo, igual que el
resto del proyecto — ver TIPO_DIA_WEEKDAYS en gtfs_schedule_builder.py):
un tren pertenece a un grupo si alguno de sus weekdays resueltos cae en él
(p. ej. un tren que circula miércoles y domingo aparece tanto en
"laborable" como en "domingo").

Uso:
    python3 scripts/check_gtfs_schedule_changes.py
    python3 scripts/check_gtfs_schedule_changes.py --before 2026-09-27 --after 2026-10-16
"""

import argparse
import csv
import ssl
import sys
from datetime import date, datetime
from pathlib import Path

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

# Mismo agrupamiento que TIPO_DIA_WEEKDAYS en gtfs_schedule_builder.py.
_TIPO_DIA_BUCKETS = {
    "Laborable (lun-vie)": {0, 1, 2, 3, 4},
    "Sábado": {5},
    "Domingo": {6},
}

CSV_FIELDS = [
    "tipo_dia", "sentido", "cod_comercial",
    "hora_salida_antes", "hora_llegada_antes",
    "hora_salida_despues", "hora_llegada_despues",
    "estado",
]


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _by_key(trains: list[dict]) -> dict[tuple[str, str], dict]:
    return {(t["cod_comercial"], t["sentido"]): t for t in trains}


def _in_bucket(train: dict, bucket_weekdays: set) -> bool:
    return bool(set(train["weekdays"]) & bucket_weekdays)


def _print_train(train: dict) -> str:
    return f"{train['cod_comercial']} ({train['sentido']}) {train['hora_salida']}->{train['hora_llegada_destino']}"


def build_diff_rows(tipo_dia_label: str, before: list[dict], after: list[dict]) -> list[dict]:
    """
    Una fila por cada tren visto en `before` y/o `after` para este tipo de
    día. `estado` solo se rellena para altas ("nuevo") y bajas ("cancelado")
    — un tren presente en ambos lados queda con `estado` vacío, tanto si sus
    horas no cambiaron como si cambiaron (el propio valor de las columnas de
    hora ya lo muestra, sin necesitar una tercera etiqueta).
    """
    before_by_key = _by_key(before)
    after_by_key = _by_key(after)

    rows = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        cod_comercial, sentido = key
        old = before_by_key.get(key)
        new = after_by_key.get(key)

        if old and new:
            rows.append({
                "tipo_dia": tipo_dia_label, "sentido": sentido, "cod_comercial": cod_comercial,
                "hora_salida_antes": old["hora_salida"], "hora_llegada_antes": old["hora_llegada_destino"],
                "hora_salida_despues": new["hora_salida"], "hora_llegada_despues": new["hora_llegada_destino"],
                "estado": "",
            })
        elif old and not new:
            # Eliminado: se deja el "antes" tal cual y se marca el "después"
            # como cancelado en vez de dejarlo vacío (mismo criterio que el
            # Data Lake ya usa para un tren nunca capturado, ver CLAUDE.md).
            rows.append({
                "tipo_dia": tipo_dia_label, "sentido": sentido, "cod_comercial": cod_comercial,
                "hora_salida_antes": old["hora_salida"], "hora_llegada_antes": old["hora_llegada_destino"],
                "hora_salida_despues": "cancelado", "hora_llegada_despues": "cancelado",
                "estado": "cancelado",
            })
        else:
            # Nuevo: el "antes" se deja en blanco, no existía ese tren.
            rows.append({
                "tipo_dia": tipo_dia_label, "sentido": sentido, "cod_comercial": cod_comercial,
                "hora_salida_antes": "", "hora_llegada_antes": "",
                "hora_salida_despues": new["hora_salida"], "hora_llegada_despues": new["hora_llegada_destino"],
                "estado": "nuevo",
            })

    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def diff_schedules(before: list[dict], after: list[dict]) -> bool:
    before_by_key = _by_key(before)
    after_by_key = _by_key(after)

    added = sorted(set(after_by_key) - set(before_by_key))
    removed = sorted(set(before_by_key) - set(after_by_key))
    common = sorted(set(before_by_key) & set(after_by_key))

    changed = []
    for key in common:
        old, new = before_by_key[key], after_by_key[key]
        fields_changed = [
            field for field in ("hora_salida", "hora_llegada_destino")
            if old[field] != new[field]
        ]
        if fields_changed:
            changed.append((key, old, new, fields_changed))

    if not added and not removed and not changed:
        print("  Sin cambios.")
        return False

    if added:
        print(f"  Trenes NUEVOS ({len(added)}):")
        for key in added:
            print(f"    + {_print_train(after_by_key[key])}")

    if removed:
        print(f"  Trenes ELIMINADOS ({len(removed)}):")
        for key in removed:
            print(f"    - {_print_train(before_by_key[key])}")

    if changed:
        print(f"  Trenes con CAMBIOS ({len(changed)}):")
        for key, old, new, fields_changed in changed:
            print(f"    * {key[0]} ({key[1]}):")
            for field in fields_changed:
                print(f"        {field}: {old[field]} -> {new[field]}")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", default=date.today().isoformat(),
                         help="Fecha 'antes' (YYYY-MM-DD) contra la que resolver el patrón semanal, por defecto hoy")
    parser.add_argument("--after", default="2026-10-16",
                         help="Fecha 'después' (YYYY-MM-DD) contra la que resolver el patrón semanal, por defecto 2026-10-16")
    parser.add_argument("--zamora-code", default=ZAMORA_CODE)
    parser.add_argument("--chamartin-code", default=CHAMARTIN_CODE)
    parser.add_argument("--csv", default="gtfs_schedule_diff.csv",
                         help="Ruta del CSV de salida (por defecto gtfs_schedule_diff.csv)")
    args = parser.parse_args()

    before_date = _parse_date(args.before)
    after_date = _parse_date(args.after)
    log_extra = {"script": "check_gtfs_schedule_changes"}

    print("Descargando GTFS estático de Renfe...")
    gtfs_files = GtfsClient(log_extra).download_and_extract()

    print(f"Resolviendo patrón semanal para {before_date.isoformat()}...")
    before_all = build_schedule_reference(gtfs_files, before_date, args.zamora_code, args.chamartin_code, log_extra)

    print(f"Resolviendo patrón semanal para {after_date.isoformat()}...")
    after_all = build_schedule_reference(gtfs_files, after_date, args.zamora_code, args.chamartin_code, log_extra)

    any_changes = False
    all_rows = []
    for label, bucket_weekdays in _TIPO_DIA_BUCKETS.items():
        before_trains = [t for t in before_all if _in_bucket(t, bucket_weekdays)]
        after_trains = [t for t in after_all if _in_bucket(t, bucket_weekdays)]

        print(f"\n== {label}: {before_date.isoformat()} -> {after_date.isoformat()} ==")
        print(f"  {len(before_trains)} trenes -> {len(after_trains)} trenes")

        if diff_schedules(before_trains, after_trains):
            any_changes = True

        all_rows.extend(build_diff_rows(label, before_trains, after_trains))

    tipo_dia_order = {label: i for i, label in enumerate(_TIPO_DIA_BUCKETS)}
    all_rows.sort(key=lambda r: (tipo_dia_order[r["tipo_dia"]], r["hora_salida_antes"], r["hora_salida_despues"]))

    csv_path = Path(args.csv)
    write_csv(all_rows, csv_path)
    print(f"\nCSV escrito en {csv_path.resolve()} ({len(all_rows)} filas).")

    print()
    if any_changes:
        print("Se han detectado cambios de horario en el GTFS entre las dos fechas comparadas.")
    else:
        print("El GTFS de Renfe no refleja (todavía) ningún cambio de horario entre las dos fechas comparadas.")

    return 1 if any_changes else 0


if __name__ == "__main__":
    sys.exit(main())
