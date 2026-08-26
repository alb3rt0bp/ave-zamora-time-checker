"""
Fixtures de un GTFS estático en miniatura, con las mismas columnas y
convenciones observadas en el feed real de Renfe (AV/Larga Distancia) — ver
la cabecera de gtfs_schedule_builder.py para el detalle de esas convenciones.

Los trip_id/service_id están pensados para MONDAY (2026-01-05, "laborable")
y SUNDAY (2026-01-04, "domingo") de tests/dummies/reference_dates.py:

- TRIP_M1 (cod_comercial 04154, Madrid): servicio SVC_LABORABLE, activo
  también en MONDAY. Zamora seq=04 (dep 07:41), Chamartín seq=05 (arr 08:49)
  → Chamartín después de Zamora → sentido Madrid.
- TRIP_G1 (cod_comercial 04505, Galicia): servicio SVC_SUNDAY_ONLY, cuyo
  calendar.txt está en 0000000 pero calendar_dates.txt lo añade solo el
  SUNDAY de este fixture. Chamartín seq=01 (dep 10:04), Zamora seq=02
  (arr 11:08) → Chamartín antes de Zamora → sentido Galicia.
- TRIP_D1 / TRIP_D2 (cod_comercial 04999, ambos Madrid, mismas horas):
  composición doble — dos trip_id distintos que deben colapsar en una única
  entrada tras el dedup de build_todays_trains.
- TRIP_NOCHAM (cod_comercial 04001): solo para en Zamora, nunca en
  Chamartín → no es un trayecto que este sistema siga, debe excluirse.
- TRIP_NOSHORTNAME: para en Zamora y Chamartín pero su fila en trips.txt no
  tiene trip_short_name → sin cod_comercial que asignar, debe excluirse.
- TRIP_REMOVED (cod_comercial 04222): servicio SVC_REMOVED_TODAY, activo por
  calendar.txt en MONDAY, pero calendar_dates.txt lo quita ese día concreto
  (exception_type=2) → debe excluirse pese al calendario.
- TRIP_OUTOFRANGE (cod_comercial 04333): servicio SVC_OUTOFRANGE, activo por
  patrón semanal pero con start_date/end_date que no cubren MONDAY/SUNDAY.
"""

ZAMORA_CODE = "30200"
CHAMARTIN_CODE = "17000"

STOP_TIMES_CSV = """trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled
TRIP_M1,7:39:00,7:41:00,30200,04,,0,0,
TRIP_M1,8:49:00,8:49:00,17000,05,,1,0,
TRIP_G1,10:04:00,10:04:00,17000,01,,0,1,
TRIP_G1,11:08:00,11:10:00,30200,02,,0,0,
TRIP_D1,7:39:00,7:41:00,30200,04,,0,0,
TRIP_D1,8:49:00,8:49:00,17000,05,,1,0,
TRIP_D2,7:39:00,7:41:00,30200,02,,0,0,
TRIP_D2,8:49:00,8:49:00,17000,03,,1,0,
TRIP_NOCHAM,9:00:00,9:00:00,30200,01,,0,1,
TRIP_NOSHORTNAME,7:00:00,7:02:00,30200,01,,0,0,
TRIP_NOSHORTNAME,8:00:00,8:00:00,17000,02,,1,0,
TRIP_REMOVED,7:00:00,7:02:00,30200,01,,0,0,
TRIP_REMOVED,8:00:00,8:00:00,17000,02,,1,0,
TRIP_OUTOFRANGE,7:00:00,7:02:00,30200,01,,0,0,
TRIP_OUTOFRANGE,8:00:00,8:00:00,17000,02,,1,0,
"""

TRIPS_CSV = """route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id,wheelchair_accessible
R1,SVC_LABORABLE,TRIP_M1,,04154,,,,1
R2,SVC_SUNDAY_ONLY,TRIP_G1,,04505,,,,1
R3,SVC_LABORABLE,TRIP_D1,,04999,,,,1
R3,SVC_LABORABLE,TRIP_D2,,04999,,,,1
R4,SVC_LABORABLE,TRIP_NOCHAM,,04001,,,,1
R5,SVC_LABORABLE,TRIP_NOSHORTNAME,,,,,,1
R6,SVC_REMOVED_TODAY,TRIP_REMOVED,,04222,,,,1
R7,SVC_OUTOFRANGE,TRIP_OUTOFRANGE,,04333,,,,1
"""

CALENDAR_CSV = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
SVC_LABORABLE,1,1,1,1,1,1,1,20260101,20260131
SVC_SUNDAY_ONLY,0,0,0,0,0,0,0,20260101,20260131
SVC_REMOVED_TODAY,1,1,1,1,1,1,1,20260101,20260131
SVC_OUTOFRANGE,1,1,1,1,1,1,1,20260201,20260228
"""

CALENDAR_DATES_CSV = """service_id,date,exception_type
SVC_SUNDAY_ONLY,20260104,1
SVC_REMOVED_TODAY,20260105,2
"""

GTFS_FILES = {
    "stop_times.txt": STOP_TIMES_CSV,
    "trips.txt": TRIPS_CSV,
    "calendar.txt": CALENDAR_CSV,
    "calendar_dates.txt": CALENDAR_DATES_CSV,
}


def to_zip_bytes(files: dict = GTFS_FILES) -> bytes:
    """
    Empaqueta `files` como el zip que gtfs_client.py espera descargar de
    Renfe — para tests de integración que mockean urllib.request.urlopen
    con el zip completo en vez de con los CSV ya parseados.
    """
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()
