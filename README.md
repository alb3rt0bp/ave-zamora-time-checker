# Zamora Train Observability — AWS Architecture

Sistema de observabilidad en AWS para monitorizar la **puntualidad de los trenes
Alvia/Intercity de Renfe a su paso por la estación de Zamora**.

Los datos de retrasos alimentan un Data Lake que sirve como evidencia objetiva
para la campaña de comunicación reivindicativa (argumento central: Zamora no
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
SQS delay variable      →    DynamoDB como estado de tracking (TTL diario)
Lambda poll+reencola    →    Lambda stateless con lógica de ventana
1 JSON por tren/evento  →    1 JSONL por día (volcado diario) + Glue + Athena
```

### Arquitectura Event-Driven con ventana temporal

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             AWS Account                                    │
│                                                                            │
│  ┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐        │
│  │  EventBridge │     │   Lambda        │     │   DynamoDB       │        │
│  │  Scheduler   │────▶│  train-tracker  │────▶│  train-state     │        │
│  │  (cada 5')   │     │  (arm64/py3.12) │     │  (TTL 00:30      │        │
│  └──────────────┘     └────────┬────────┘     │   día siguiente) │        │
│                                │               └────────┬─────────┘        │
│                                ▼                        │                  │
│                       ┌────────────────┐                │ scan diario     │
│                       │  flotaLD.json  │                ▼                  │
│                       │  (Renfe API)   │     ┌──────────────────┐          │
│                       └────────────────┘     │  EventBridge     │          │
│  (sin escritura a S3 durante el polling)     │  Scheduler       │          │
│                                               │  (00:15, 1×/día) │          │
│                                               └────────┬─────────┘          │
│                                                        ▼                    │
│                                               ┌──────────────────┐          │
│                                               │  Lambda          │          │
│                                               │  daily-dump      │          │
│                                               └────────┬─────────┘          │
│                                                        ▼                    │
│                                     ┌─────────────────────────────────┐    │
│                                     │  S3 Data Lake                  │    │
│                                     │  zamora-trains/year=/month=/   │    │
│                                     │  day=/YYYY-MM-DD.jsonl (1/día) │    │
│                                     └────────┬────────────────────────┘    │
│                                              │ S3 → EventBridge             │
│                                              ▼                              │
│                                     ┌─────────────────┐   ┌───────────────┐│
│                                     │ Lambda          │──▶│  CloudWatch   ││
│                                     │ delay-metrics   │   │  Dashboard +  ││
│                                     └─────────────────┘   │  SNS Alarm    ││
│                                              │             └───────────────┘│
│                              ┌───────────────┴────────┐                     │
│                              ▼                        ▼                     │
│                     ┌────────────────┐      ┌──────────────────┐           │
│                     │   Glue Table   │─────▶│     Athena       │           │
│                     │ (sin Crawler)  │      │  (1 GB/query cap)│           │
│                     └────────────────┘      └──────────────────┘           │
│                                                                              │
│  train-tracker (cont.) — al marcar un tren "entregado" con retraso alto     │
│  (o ser el tren madrugador) publica una alerta desacoplada vía SNS:         │
│                                                                              │
│  ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐    │
│  │  SNS             │────▶│  Lambda          │────▶│  Claude Sonnet   │    │
│  │  DelayTweetTopic │     │  tweet-notifier  │     │  4.6 (Bedrock)   │    │
│  └──────────────────┘     └────────┬─────────┘     └─────────────────┘    │
│                                     │ enriquecimiento aditivo               │
│                                     ▼                                       │
│                            ┌──────────────────┐     ┌─────────────────┐    │
│                            │  xfetch.io       │     │  X API v2        │    │
│                            │  (tendencias)    │     │  (OAuth1.0a,     │    │
│                            └──────────────────┘     │  aún comentado)  │    │
│                                                       └─────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

En el primer ciclo de polling de cada día, `train-tracker` siembra en
DynamoDB un placeholder por cada tren programado hoy (`_seed_todays_trains`),
antes incluso de que haya datos reales de Renfe — así el listado de trenes
del día está disponible desde el primer momento, no solo a medida que cada
uno se va capturando.

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

### Corrección de retrasos anómalos de Renfe

`flotaLD.json` ha reportado alguna vez un `ultRetraso` disparatado (p. ej. `-562`
minutos observado en producción) — un bug puntual del servicio de Renfe, no un tren
circulando con adelanto real. Cada `ultRetraso` leído de la flota pasa por
`_sanitize_retraso` (`handler.py`) antes de usarse: si cae por debajo de
`NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES` (por defecto `-10`), se descarta y se
recalcula comparando la hora actual con la hora programada de referencia
(`hora_llegada_destino`) — así `hora_llegada_corregida`/`hora_paso_zamora`, que se
derivan de ese mismo valor, quedan corregidas automáticamente en vez de arrastrar el
dato corrupto. Cada corrección publica además un aviso por email a
`AlertEmailAddress` (vía el topic SNS `AlertTopic`, el mismo que usa la alarma de
retrasos altos) para poder revisarla manualmente.

### Redacción automática de tuits (tweet-notifier)

Cuando `train-tracker` marca un tren como entregado con más de
`DelayAlertThresholdMinutes` minutos de retraso — o es el "tren madrugador"
(`FlagshipMadridTrainCode`, por defecto `04154`, el primer tren laborable
hacia Madrid y eje de la reivindicación), que siempre
dispara alerta tenga o no retraso — publica un evento en el topic SNS
`DelayTweetTopic`. Esto desacopla la publicación del ciclo de polling: un
fallo o lentitud de Bedrock/X/xfetch nunca bloquea ni ralentiza
`train-tracker`.

La Lambda `tweet-notifier` (`lambdas/tweet_notifier/`) consume esos eventos:

- **`claude_client.py`** redacta el texto del tuit y sus hashtags con Claude
  Sonnet 4.6 en Amazon Bedrock (`invoke_model` con salida estructurada
  `json_schema`, sin el SDK de Anthropic), con un prompt que distingue tres
  situaciones (tren madrugador con retraso, tren madrugador puntual, retraso
  genérico) y fuerza siempre al menos un hashtag reivindicativo.
- **`xfetch_client.py`** añade, como enriquecimiento aditivo y no bloqueante,
  tendencias reales de X vía xfetch.io (proveedor externo, no la API
  oficial de X ni una tool de Anthropic) — si falla, el tuit se redacta
  igualmente sin ese hashtag extra.
- **`x_client.py`** implementa la publicación real en X (API v2, OAuth1.0a
  firmado a mano) pero está **comentada** en `handler.py` por ahora: el
  texto redactado solo se loguea, pendiente de activar la publicación real.

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
│   ├── deploy.sh                       # Despliegue del backend (sam build + sam deploy)
│   ├── deploy_frontend.sh             # Build + sync del frontend al bucket S3
│   └── github-oidc-role.yaml          # Rol IAM para GitHub Actions (one-shot)
├── lambdas/
│   ├── train_tracker/
│   │   ├── handler.py                 # Orquestador principal (ventana + grabación)
│   │   ├── renfe_client.py            # Cliente HTTP con caché en memoria (60s)
│   │   ├── schedule_matcher.py        # Lógica de ventana de monitorización activa
│   │   ├── datalake_writer.py         # Escritura S3 con particionado Hive
│   │   └── requirements.txt           # Solo tzdata (boto3 va en el runtime)
│   ├── delay_metrics/
│   │   └── handler.py                 # Publica métricas de retraso en CloudWatch
│   ├── api/
│   │   └── handler.py                 # API HTTP solo lectura: get_today_handler / get_day_handler
│   └── tweet_notifier/
│       ├── handler.py                 # Disparado por SNS: redacta y (por ahora) solo loguea el tuit
│       ├── claude_client.py           # draft_tweet vía Claude Sonnet 4.6 en Bedrock
│       ├── xfetch_client.py           # Tendencias reales de X desde xfetch.io (enriquecimiento)
│       ├── x_client.py                # Cliente OAuth1.0a para publicar en la API v2 de X
│       └── requirements.txt           # Solo librería estándar (boto3 va en el runtime)
├── frontend/                          # Frontend Vite + React + TypeScript
│   ├── src/
│   │   ├── api.ts                     # Cliente HTTP: fetchToday() / fetchByDate()
│   │   ├── types.ts                   # Tipos TodayTrain / DayTrain / TrainRow
│   │   ├── App.tsx                    # Selector de fecha + vista de hoy / día pasado
│   │   ├── components/                # TrainTable, DatePicker, TodayView, DayView
│   │   ├── utils/                     # formatDelay, yesterdayMadrid, normalizeTrain
│   │   └── mocks/                     # Handlers MSW usados en los tests
│   ├── package.json
│   └── vite.config.ts                 # Config de Vite + Vitest (tests y cobertura)
├── scripts/
│   ├── compile_schedules.py           # CSVs → config/train_schedules.json
│   └── query_examples.sql             # Queries Athena de ejemplo
└── .github/workflows/
    └── deploy.yml                     # CI/CD: deploy automático del backend a AWS
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

Particionado Hive por `year / month / day`. Un único fichero JSONL por día
(un tren entregado por línea), escrito una vez al día por `daily_dump_handler`:
`s3://<bucket>/zamora-trains/year=YYYY/month=MM/day=DD/YYYY-MM-DD.jsonl`. Con
Athena sin capa gratuita, menos objetos = menos overhead por consulta.

```json
{
  "event_id": "04154-2024-11-15T07:41",
  "cod_comercial": "04154",
  "sentido": "Madrid",
  "tipo_dia": "laborable",
  "dia_semana": "Friday",
  "hora_programada": "07:41",
  "hora_llegada_corregida": "07:47",
  "minutos_retraso": 6
}
```

---

## Infraestructura (SAM / CloudFormation)

`infrastructure/template.yaml` despliega:

- **S3 Data Lake** — versionado, cifrado (AES256), acceso público bloqueado y
  lifecycle (→ Standard-IA a 30 días, → Glacier-IR a 90). EventBridge habilitado
  para notificar nuevos objetos.
- **DynamoDB `zamora-train-state`** — on-demand (PAY_PER_REQUEST), TTL hasta las
  00:30 del día siguiente (margen tras el último ciclo de polling y antes del
  volcado diario), Point-in-Time Recovery. Clave simple `pk = {cod}#{fecha}`.
- **Lambda `train-tracker`** — arm64/Graviton2, Python 3.12, 256 MB, timeout 60s.
  Disparada por EventBridge Scheduler `rate(5 minutes)`. Siembra los trenes
  del día en el primer ciclo y actualiza su estado en DynamoDB; no escribe en S3.
- **Lambda `daily-dump`** — arm64/Graviton2, Python 3.12. Disparada una vez al
  día a las 00:15 (hora de Madrid). Escanea DynamoDB, coge los trenes del día
  anterior marcados como `entregado` y escribe un único fichero JSONL en S3.
- **Lambda `delay-metrics`** — disparada por EventBridge cuando se crea un objeto
  en `zamora-trains/`. Lee el JSONL del día (una línea por tren) y publica
  métricas en el namespace CloudWatch `ZamoraTrains`
  (`TrainDelayMinutes`, `TrainPassage`, `TrainsWithDelay`).
- **Glue Database + Table** — la tabla `zamora_trains` se define a mano en el
  template (sin Crawler), con columnas que reflejan exactamente el JSON que
  escribe `daily_dump_handler()`. Las particiones se resuelven vía Partition
  Projection (year/month/day), así que los datos nuevos aparecen en Athena
  sin ningún paso adicional tras el despliegue.
- **Athena Workgroup** — cap de 1 GB escaneado por query, resultados en el propio bucket.
- **CloudWatch Dashboard** — retraso medio diario, trenes con retraso, invocaciones/errores.
- **SNS + CloudWatch Alarm** (opcional) — `AlertTopic` envía email a `AlertEmailAddress`
  cuando un retraso supera 30 min (`HighDelayAlarm`) y también cuando `train-tracker`
  detecta un `ultRetraso` anómalo de Renfe (ver arriba). Solo se crea si se pasa
  `AlertEmailAddress` (por defecto ya trae un valor).
- **SNS `DelayTweetTopic`** — desacopla `train-tracker` de la redacción del
  tuit; se crea siempre (no depende de `AlertEmailAddress`).
- **Lambda `tweet-notifier`** — disparada por `DelayTweetTopic`. Redacta el
  tuit con Claude Sonnet 4.6 en Bedrock más tendencias de xfetch.io; por
  ahora solo loguea el resultado (ver arriba). Necesita permisos extra sobre
  Bedrock (`InvokeModel` sobre el inference profile *y* el foundation model,
  ya que Sonnet 4.6 solo se sirve vía cross-region inference) y sobre AWS
  Marketplace (`ViewSubscriptions`/`Subscribe`, sin scoping por recurso —
  la suscripción a modelos de Anthropic en Bedrock pasa por Marketplace por
  debajo).
- **Secrets Manager `XApiCredentialsSecret` / `XfetchApiKeySecret`** —
  placeholders creados vacíos por el template; las credenciales OAuth1.0a
  de la X Developer App y la API key de xfetch.io se rellenan a mano tras
  el despliegue (consola o CLI), nunca en el template.
- **API HTTP `TrainsApi`** (API Gateway HttpApi, CORS abierto) — dos Lambdas de solo
  lectura sobre el mismo API, pensado para colgar aquí futuras rutas (métricas Athena,
  sugerencias de corrección) sin volver a aprovisionar nada:
  - **`GET /trains/today`** (`GetTodayTrainsFunction`) — escanea DynamoDB y devuelve
    los trenes de hoy (datos en vivo/parciales del día en curso).
  - **`GET /trains/{date}`** (`GetDayTrainsFunction`) — lee el JSONL de un día pasado
    desde el Data Lake en S3; devuelve 404 si ese día aún no se ha volcado.
- **`FrontendBucket`** — bucket S3 con website hosting habilitado (`index.html` como
  index y error document, para el fallback de la SPA) y lectura pública, para servir
  el frontend estático sin CloudFront por ahora.

### Variables de entorno / parámetros

| Parámetro | Env var Lambda | Default | Notas |
|-----------|----------------|---------|-------|
| `Environment` | `ENVIRONMENT` | `prod` | `dev` / `staging` / `prod` |
| `ZamoraStationCode` | `ZAMORA_STATION_CODE` | ver ⚠️ | Código de Zamora en Renfe |
| `ChamartinStationCode` | `CHAMARTIN_STATION_CODE` | `17000` | Detección de llegada a Madrid |
| `PollingWindowMinutes` | (config JSON) | `30` | Ventana ± en minutos |
| `AlertEmailAddress` | `DATA_QUALITY_ALERT_SNS_TOPIC_ARN` (indirecto, vía `AlertTopic`) | `albertobp@gmail.com` | Si vacío, no se crea `AlertTopic` ni la alarma SNS |
| `NegativeDelayAnomalyThresholdMinutes` | `NEGATIVE_DELAY_ANOMALY_THRESHOLD_MINUTES` | `-10` | Umbral por debajo del cual un `ultRetraso` se considera bug de Renfe y se recalcula |
| `DelayAlertThresholdMinutes` | `DELAY_ALERT_THRESHOLD_MINUTES` | `15` | Retraso mínimo (min) al marcar un tren entregado para publicar alerta de tuit |
| `FlagshipMadridTrainCode` | `FLAGSHIP_MADRID_TRAIN_CODE` | `04154` | Tren madrugador: dispara alerta de tuit siempre, tenga o no retraso |
| `ClaudeModelId` | `CLAUDE_MODEL_ID` | `global.anthropic.claude-sonnet-4-6` | Modelo Bedrock (inference profile) usado por `tweet_notifier` |
| `GtfsRtEnrichmentEnabled` | `GTFS_RT_ENRICHMENT_ENABLED` | `false` | Activa el enriquecimiento aditivo con el feed GTFS-RT oficial de Renfe |
| `GtfsScheduleEnabled` | `GTFS_SCHEDULE_ENABLED` | `false` | Resuelve el horario del día desde el GTFS estático de Renfe en vez de `train_schedules.json` (fallback si falla) |
| `GtfsZipUrl` | `GTFS_ZIP_URL` | URL del GTFS estático | Solo relevante si `GtfsScheduleEnabled=true` |
| — | `XFETCH_TRENDS_ENABLED` | `true` | Activa el enriquecimiento con tendencias reales de xfetch.io en `tweet_notifier` |

---

## Códigos de estación

`ZAMORA_STATION_CODE=30200` y `CHAMARTIN_STATION_CODE=17000` — códigos
públicos Adif/Renfe, confirmados vía 5 fuentes independientes (páginas de
estación de Adif, dataset oficial de estaciones de `data.renfe.com`, un tren
en vivo en `flotaLD.json` con `codEstSig=30200` a ~1km de Zamora,
`trenesConEstacionesLD.json` y el feed GTFS-Realtime oficial — ver
CLAUDE.md para el detalle). `deploy.sh` y `template.yaml` ya despliegan
ambos con `30200`. Pendiente recomendado: confirmar una captura real en
CloudWatch Logs tras el despliegue.

---

## Despliegue

El despliegue tiene dos partes independientes: primero el backend (stack SAM
completo, incluye la API HTTP y el bucket del frontend), y después el frontend
(build estático sincronizado a ese bucket). El frontend **no puede desplegarse
sin que el backend ya exista** — necesita leer la URL del API y el nombre del
bucket de los outputs del stack.

### 1. Rol de despliegue (una sola vez por cuenta)

`infrastructure/github-oidc-role.yaml` crea el proveedor OIDC de GitHub y el rol
`github-actions-zamora-trains-deploy`. Desplegarlo manualmente una vez y configurar su
ARN como secret `AWS_DEPLOY_ROLE_ARN` en los *environments* `dev`/`prod` de GitHub.

### 2. Despliegue del backend

```bash
./infrastructure/deploy.sh dev
./infrastructure/deploy.sh prod --alert-email tu@email.com
```

Requisitos: `aws-cli` v2, `sam-cli`, Python 3.12, permisos de despliegue en AWS.

El script compila los horarios, crea el bucket de artefactos SAM, hace `sam build`
(en contenedor) + `sam deploy`, y muestra los outputs — incluidos `ApiBaseUrl`,
`FrontendBucketName` y `FrontendDistributionId`/`FrontendDistributionDomainName`
(o `FrontendCustomDomainUrl` si hay dominio propio), que necesita el paso
siguiente. La tabla Athena queda lista para consultar inmediatamente, sin pasos
adicionales. Región por defecto: `eu-south-2` (España).

Para poner el frontend bajo un dominio propio (p.ej. `zamorave.com`) con HTTPS,
ver [`infrastructure/DOMAIN_SETUP.md`](infrastructure/DOMAIN_SETUP.md) — añade
los flags `--domain`/`--hosted-zone-id`/`--certificate-arn` a `deploy.sh`.

### 3. Despliegue del frontend

```bash
./infrastructure/deploy_frontend.sh dev
```

Requisitos: `aws-cli` v2, Node.js/npm (instalar con [nvm](https://github.com/nvm-sh/nvm)
o Homebrew). Debe ejecutarse **después** de `deploy.sh` para ese mismo entorno: el
script lee `ApiBaseUrl` y `FrontendBucketName` del stack (`aws cloudformation
describe-stacks`) y falla con un mensaje claro si el stack todavía no existe.

Pasos que ejecuta: `npm ci` en `frontend/`, `npm run build` inyectando la URL del
API como `VITE_API_BASE_URL` (variable de entorno de Vite, solo en build time),
`aws s3 sync dist/ s3://<bucket>/ --delete` e invalida la caché de CloudFront
(`aws cloudfront create-invalidation`, necesario porque el bucket ya no es
público — se sirve vía CloudFront con Origin Access Control). Al final imprime
la URL pública del frontend (dominio propio si está configurado, si no el
`*.cloudfront.net`). La API queda expuesta en el mismo dominio bajo `/api`
(sin el stage `/prod`/`/dev` visible en el path), así que en producción no hace
falta CORS entre frontend y API — son same-origin.

Para desarrollo local del frontend contra una API ya desplegada:

```bash
cd frontend
npm install
npm run dev              # usa VITE_API_BASE_URL de .env.development
```

### 4. CI/CD (GitHub Actions)

`.github/workflows/deploy.yml` despliega automáticamente el **backend** en cada push,
autenticándose vía OIDC (sin claves de larga duración):

- push a **`main`** → environment/stack **`prod`**
- push a **`develop`** → environment/stack **`dev`**

El despliegue del frontend (`deploy_frontend.sh`) todavía no está integrado en este
workflow — por ahora se ejecuta a mano tras cada despliegue de backend relevante.

---

## Consultas

Ver `scripts/query_examples.sql` para queries Athena listas para usar. La base
de datos Glue lleva sufijo de entorno (`zamora_trains_db_prod`,
`zamora_trains_db_dev`, ...). Ejemplo rápido en prod:

```sql
SELECT * FROM zamora_trains_db_prod.zamora_trains LIMIT 10;
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

### Consulta diaria de horarios 
https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip