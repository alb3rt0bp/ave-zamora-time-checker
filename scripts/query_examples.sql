-- ============================================================
-- query_examples.sql
-- Queries Athena para el Data Lake de trenes Zamora
-- Workgroup: zamora-trains-{Environment} (p.ej. zamora-trains-prod)
-- Database:  zamora_trains_db_{Environment} (p.ej. zamora_trains_db_prod) —
--            usa USE zamora_trains_db_prod; antes de estas queries, o
--            cualifica cada FROM zamora_trains como database.zamora_trains
-- Table:     zamora_trains (definida en infrastructure/template.yaml, sin Crawler)
-- ============================================================

-- ── 1. Retraso medio por sentido (último mes) ────────────────────────────────
SELECT
    sentido,
    AVG(minutos_retraso)                    AS retraso_medio_min,
    MAX(minutos_retraso)                    AS retraso_max_min,
    COUNT(*)                                AS total_pasos,
    SUM(CASE WHEN minutos_retraso > 0 THEN 1 ELSE 0 END) AS pasos_con_retraso,
    ROUND(
        100.0 * SUM(CASE WHEN minutos_retraso > 0 THEN 1 ELSE 0 END) / COUNT(*), 1
    ) AS pct_con_retraso
FROM zamora_trains
WHERE year = CAST(YEAR(CURRENT_DATE) AS VARCHAR)
  AND month = LPAD(CAST(MONTH(CURRENT_DATE) AS VARCHAR), 2, '0')
GROUP BY sentido
ORDER BY sentido;


-- ── 2. Ranking de trenes más puntuales / retrasados ──────────────────────────
SELECT
    cod_comercial,
    sentido,
    COUNT(*)                    AS pasos_registrados,
    AVG(minutos_retraso)        AS retraso_medio,
    MAX(minutos_retraso)        AS retraso_maximo,
    MIN(minutos_retraso)        AS retraso_minimo
FROM zamora_trains
WHERE year >= '2024'
GROUP BY cod_comercial, sentido
ORDER BY retraso_medio DESC;


-- ── 3. Retraso por día de la semana ─────────────────────────────────────────
SELECT
    dia_semana,
    tipo_dia,
    sentido,
    COUNT(*)             AS pasos,
    AVG(minutos_retraso) AS retraso_medio
FROM zamora_trains
GROUP BY dia_semana, tipo_dia, sentido
ORDER BY
    CASE dia_semana
        WHEN 'Monday'    THEN 1
        WHEN 'Tuesday'   THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday'  THEN 4
        WHEN 'Friday'    THEN 5
        WHEN 'Saturday'  THEN 6
        WHEN 'Sunday'    THEN 7
    END,
    sentido;


-- ── 4. Serie temporal diaria de retraso medio ────────────────────────────────
SELECT
    year,
    month,
    day,
    sentido,
    COUNT(*)             AS pasos,
    AVG(minutos_retraso) AS retraso_medio,
    MAX(minutos_retraso) AS retraso_maximo
FROM zamora_trains
GROUP BY year, month, day, sentido
ORDER BY year, month, day, sentido;


-- ── 5. Días con retraso extremo (> 30 min) ──────────────────────────────────
SELECT
    year,
    month,
    day,
    cod_comercial,
    sentido,
    hora_programada,
    hora_llegada_corregida,
    minutos_retraso
FROM zamora_trains
WHERE minutos_retraso > 30
ORDER BY minutos_retraso DESC
LIMIT 50;


-- ── 6. Comparativa puntualidad: sentido Madrid vs Galicia ────────────────────
SELECT
    year,
    month,
    sentido,
    ROUND(AVG(minutos_retraso), 1) AS retraso_medio,
    APPROX_PERCENTILE(minutos_retraso, 0.5)  AS percentil_50,
    APPROX_PERCENTILE(minutos_retraso, 0.9)  AS percentil_90,
    APPROX_PERCENTILE(minutos_retraso, 0.95) AS percentil_95
FROM zamora_trains
GROUP BY year, month, sentido
ORDER BY year, month, sentido;


-- ── 7. Análisis de tendencia mensual ────────────────────────────────────────
WITH monthly AS (
    SELECT
        year,
        month,
        AVG(minutos_retraso) AS retraso_medio
    FROM zamora_trains
    GROUP BY year, month
)
SELECT
    year,
    month,
    ROUND(retraso_medio, 2) AS retraso_medio,
    ROUND(
        retraso_medio - LAG(retraso_medio) OVER (ORDER BY year, month), 2
    ) AS variacion_vs_mes_anterior
FROM monthly
ORDER BY year, month;
