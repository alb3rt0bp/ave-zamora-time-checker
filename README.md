# Zamora Train Observability — AWS Architecture

Sistema de observabilidad en AWS para monitorizar la **puntualidad de los trenes
Alvia/Intercity de Renfe a su paso por la estación de Zamora**. Construido para la
**Asociación de Usuarios de Trenes AVE de Zamora**.

Los datos de retrasos alimentan un Data Lake que sirve como evidencia objetiva
para la campaña de comunicación de la asociación (argumento central: Zamora no
tiene ningún tren de primera hora que llegue a Madrid Chamartín antes de las 08:00
en día laborable, mientras que Salamanca, Segovia y Valladolid sí).

### Endpoints de Renfe (tiempo real)

- **Flota en circulación**: https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json
- **Trenes con secuencia de estaciones y hora de paso planificada**: https://tiempo-real.largorecorrido.renfe.com/renfe-visor/trenesConEstacionesLD.json
- **Llegadas Madrid Chamartín (Adif)**: portal Adif, estación `17000`

---

## Decisiones de Arquitectura (AWS Professional Architect)

### ⚠️ Por qué NO usar EventBridge + SQS delay para polling

La propuesta inicial (un EventBridge por cada hora de paso) tiene un problema de fondo:
el endpoint `flotaLD.json` **no es un webhook push**, es un fichero JSON que se actualiza
periódicamente. Hacer polling desde SQS con delay variable introduce deriva temporal y
complejidad innecesaria. La alternativa adoptada es más robusta:

```
PROPUESTA ORIGINAL:          ARQUITECTURA ADOPTADA:
─────────────────────────    ─────────────────────────────────────────
EventBridge × N trenes  →    EventBridge Scheduler (1 regla cada 5')
SQS delay variable      →    DynamoDB como estado de tracking (TTL 24h)
Lambda poll+reencola    →    Lambda stateless con lógica de ventana
JSON files              →    S3 Data Lake + Glue + Athena
```

### Arquitectura Event-Driven con ventana temporal

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             AWS Account                                    │
│                                                                            │
│  ┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐        │
│  │  EventBridge │     │   Lambda        │     │   DynamoDB       │        │
│  │  Scheduler   │────▶│  train-tracker  │────▶│  train-state     │        │
│  │  (cada 5')   │     │  (arm64/py3.12) │     │  (TTL 24h)       │        │
│  └──────────────┘     └────────┬────────┘     └──────────────────┘        │
│                                │                                           │
│                     ┌──────────┴──────────┐                               │
│                     ▼                     ▼                               │
│            ┌────────────────┐   ┌─────────────────┐                       │
│            │  flotaLD.json  │   │  S3 Data Lake   │                       │
│            │  (Renfe API)   │   │  zamora-trains/ │                       │
│            └────────────────┘   │  year=/month=/  │                       │
│                                 │  day=/*.json    │                       │
│                                 └────────┬────────┘                       │
│                                          │ S3 → EventBridge               │
│                                          ▼                                 │
│                                 ┌─────────────────┐   ┌───────────────┐   │
│                                 │ Lambda          │──▶│  CloudWatch   │   │
│                                 │ delay-metrics   │   │  Dashboard +  │   │
│                                 └─────────────────┘   │  SNS Alarm    │   │
│                                          │            └───────────────┘   │
│                          ┌───────────────┴────────┐                       │
│                          ▼                        ▼                        │
│                 ┌────────────────┐      ┌──────────────────┐              │
│                 │  Glue Crawler  │─────▶│     Athena       │              │
│                 │  (diario 3AM)  │      │  (1 GB/query cap)│              │
│                 └────────────────┘      └──────────────────┘              │
└──────────────────────────────────────────────────────────────────────────┘
```

### Ventana de monitorización activa

En lugar de lanzar una Lambda por cada tren y reencolar con delay, la Lambda se ejecuta
**cada 5 minutos** y comprueba qué trenes están dentro de su ventana activa. La ventana
va desde `hora_programada − 30 min` hasta `hora_programada + 30 min + 60 min` (el buffer
de 60 min cubre retrasos habituales de Renfe). Solo esos trenes se consultan en la flota.

Ventajas:
- 1 Lambda execution cada 5 min → ~288 ejecuciones/día (vs. N×reencolas)
- DynamoDB guarda el estado: si un tren ya fue registrado hoy (`done=true`), no se repite
- Sin deriva temporal por delays de SQS
- Coste mínimo (dentro del free tier en la mayoría de casos)

### Punto de grabación según el sentido

El evento se registra en el Data Lake en momentos distintos según la dirección del tren:

- **Sentido Galicia**: se graba cuando el tren pasa por Zamora, detectado porque
  `codEstAnt == ZAMORA_STATION_CODE`.
- **Sentido Madrid**: se graba cuando el tren **llega a Madrid Chamartín**, detectado por
  cualquiera de estas dos vías:
  1. `codEstAnt == CHAMARTIN_STATION_CODE`, o
  2. el tren **desaparece de la flota** habiendo sido visto en una ejecución anterior
     (existe estado en DynamoDB) → se usa el último estado conocido.

---

## Estructura del proyecto

```
ave-zamora-time-checker/
├── CLAUDE.md                          # Contexto del proyecto para agentes
├── README.md                          # Este fichero
├── config/
│   └── train_schedules.json           # 54 horarios compilados (fuente de verdad)
├── data/                              # CSVs originales de horarios (6 ficheros)
│   ├── trenes_ida_madrid_{laborable,sabado,domingo}.csv
│   └── trenes_vuelta_madrid_{laborable,sabado,domingo}.csv
├── infrastructure/
│   ├── template.yaml                  # SAM / CloudFormation (stack de la app)
│   ├── deploy.sh                       # Despliegue con sam build + sam deploy
│   └── github-oidc-role.yaml          # Rol IAM para GitHub Actions (one-shot)
├── lambdas/
│   ├── train_tracker/
│   │   ├── handler.py                 # Orquestador principal (ventana + grabación)
│   │   ├── renfe_client.py            # Cliente HTTP con caché en memoria (60s)
│   │   ├── schedule_matcher.py        # Lógica de ventana de monitorización activa
│   │   ├── datalake_writer.py         # Escritura S3 con particionado Hive
│   │   └── requirements.txt           # Solo tzdata (boto3 va en el runtime)
│   └── delay_metrics/
│       └── handler.py                 # Publica métricas de retraso en CloudWatch
├── scripts/
│   ├── compile_schedules.py           # CSVs → config/train_schedules.json
│   └── query_examples.sql             # Queries Athena de ejemplo
└── .github/workflows/
    └── deploy.yml                     # CI/CD: deploy automático a AWS
```

---

## Trenes monitorizados

54 entradas compiladas desde 6 CSVs de Renfe (`data/`) hacia `config/train_schedules.json`:

| Sentido | Tipo de día | Nº trenes |
|---------|-------------|-----------|
| Madrid  | Laborable   | 10        |
| Madrid  | Sábado      | 7         |
| Madrid  | Domingo     | 9         |
| Galicia | Laborable   | 11        |
| Galicia | Sábado      | 8         |
| Galicia | Domingo     | 9         |

Cada entrada del JSON tiene la forma:

```json
{
  "cod_comercial": "04475",
  "sentido": "Galicia",
  "tipo_dia": "domingo",
  "weekdays": [6],
  "hora_paso_zamora": "08:19",
  "hora_llegada_destino": "09:32",
  "duracion_raw": "1 h. 13 min."
}
```

Para recompilar tras editar los CSVs: `python3 scripts/compile_schedules.py`.
El `deploy.sh` también lo ejecuta automáticamente y copia el resultado a
`lambdas/train_tracker/train_schedules.json` para empaquetarlo con la Lambda.

---

## Schema del Data Lake (S3 + Athena)

Particionado Hive por `year / month / day`. Cada evento es un JSON de una línea en
`s3://<bucket>/zamora-trains/year=YYYY/month=MM/day=DD/<cod>_<sentido>_<ts>.json`:

```json
{
  "event_id": "04154-2024-11-15T07:41",
  "cod_comercial": "04154",
  "sentido": "Madrid",
  "tipo_dia": "laborable",
  "dia_semana": "Friday",
  "fecha_hora_evento": "2024-11-15T07:47:23+01:00",
  "hora_programada_zamora": "07:41",
  "hora_real_zamora": "07:47",
  "minutos_retraso": 6,
  "cod_est_ant": "71801",
  "ult_retraso_renfe": 6,
  "capturado_en_zamora": true
}
```

---

## Infraestructura (SAM / CloudFormation)

`infrastructure/template.yaml` despliega:

- **S3 Data Lake** — versionado, cifrado (AES256), acceso público bloqueado y
  lifecycle (→ Standard-IA a 30 días, → Glacier-IR a 90). EventBridge habilitado
  para notificar nuevos objetos.
- **DynamoDB `zamora-train-state`** — on-demand (PAY_PER_REQUEST), TTL 24h,
  Point-in-Time Recovery. Clave `pk = {cod}#{fecha}`, `sk = TRACKING`.
- **Lambda `train-tracker`** — arm64/Graviton2, Python 3.12, 256 MB, timeout 60s.
  Disparada por EventBridge Scheduler `rate(5 minutes)`.
- **Lambda `delay-metrics`** — disparada por EventBridge cuando se crea un objeto
  en `zamora-trains/`. Publica métricas en el namespace CloudWatch `ZamoraTrains`
  (`TrainDelayMinutes`, `TrainPassage`, `TrainsWithDelay`).
- **Glue Database + Crawler** — el crawler indexa particiones nuevas a diario a las 3:00 AM.
- **Athena Workgroup** — cap de 1 GB escaneado por query, resultados en el propio bucket.
- **CloudWatch Dashboard** — retraso medio diario, trenes con retraso, invocaciones/errores.
- **SNS + CloudWatch Alarm** (opcional) — alerta por email si un retraso supera 30 min.
  Solo se crea si se pasa `AlertEmailAddress`.

### Variables de entorno / parámetros

| Parámetro | Env var Lambda | Default | Notas |
|-----------|----------------|---------|-------|
| `Environment` | `ENVIRONMENT` | `prod` | `dev` / `staging` / `prod` |
| `ZamoraStationCode` | `ZAMORA_STATION_CODE` | ver ⚠️ | Código de Zamora en Renfe |
| `ChamartinStationCode` | `CHAMARTIN_STATION_CODE` | `17000` | Detección de llegada a Madrid |
| `PollingWindowMinutes` | (config JSON) | `30` | Ventana ± en minutos |
| `AlertEmailAddress` | — | `""` | Si vacío, no se crea la alarma SNS |
| `GlueDatabaseName` | — | `zamora_trains_db` | Base de datos Glue |

---

## ⚠️ Pendiente crítico antes de producción

Los códigos de estación deben **verificarse empíricamente** contra el campo `codEstAnt`
de `flotaLD.json` mientras un tren pasa realmente por la estación, ya que Renfe puede usar
un identificador interno distinto del público:

- **Zamora**: `deploy.sh` despliega con `71801` (también el default del `handler.py`),
  mientras que el default del `template.yaml` es `30200`. Confirmar cuál es el correcto
  antes de fijarlo.
- **Chamartín**: `17000` (usado para detectar la llegada de los trenes con sentido Madrid).

---

## Despliegue

### 1. Rol de despliegue (una sola vez por cuenta)

`infrastructure/github-oidc-role.yaml` crea el proveedor OIDC de GitHub y el rol
`github-actions-zamora-trains-deploy`. Desplegarlo manualmente una vez y configurar su
ARN como secret `AWS_DEPLOY_ROLE_ARN` en los *environments* `dev`/`prod` de GitHub.

### 2. Despliegue manual

```bash
./infrastructure/deploy.sh dev
./infrastructure/deploy.sh prod --alert-email tu@email.com
```

El script compila los horarios, crea el bucket de artefactos SAM, hace `sam build`
(en contenedor) + `sam deploy`, muestra los outputs y arranca el Glue Crawler.
Región por defecto: `eu-south-2` (España).

### 3. CI/CD (GitHub Actions)

`.github/workflows/deploy.yml` despliega automáticamente en cada push, autenticándose
vía OIDC (sin claves de larga duración):

- push a **`main`** → environment/stack **`prod`**
- push a **`develop`** → environment/stack **`dev`**

---

## Consultas

Ver `scripts/query_examples.sql` para queries Athena listas para usar. Ejemplo rápido:

```sql
SELECT * FROM zamora_trains_db.zamora_trains LIMIT 10;
```

---

## Convenciones de código

- Python 3.12, type hints donde aportan claridad.
- Toda la configuración vía variables de entorno (nunca hardcodeada).
- Lambda arm64/Graviton2 (~20% más barato que x86).
- DynamoDB on-demand (tráfico muy bajo, < 300 escrituras/día).
- Logging con `logger.info/warning/error`, nunca `print()`.
- Timezone `Europe/Madrid` vía `zoneinfo` (built-in desde Python 3.9).
- Los errores de red se registran y la Lambda retorna con gracia — la siguiente
  ejecución (5 min después) reintenta automáticamente.
```
