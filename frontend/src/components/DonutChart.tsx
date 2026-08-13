import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, type TooltipContentProps } from "recharts";
import type { DelayBuckets } from "../types";
import { DELAY_BUCKET_ORDER, formatDelayBucketLabel, type DelayBucketKey } from "../utils/metricsFormat";

interface DonutChartProps {
  buckets: DelayBuckets;
  thresholdMinutes?: number;
}

interface Slice {
  key: DelayBucketKey;
  label: string;
  value: number;
  pct: number;
  color: string;
}

// Rampa de severidad fija (puntual→grave), reutilizando los tokens de
// estado ya existentes en la app en vez de una paleta categórica nueva:
// esto es un dato de estado (bueno→crítico), no identidad de serie.
const BUCKET_COLOR_VAR: Record<DelayBucketKey, string> = {
  puntual: "var(--status-ok)",
  leve: "var(--status-mild)",
  significativo: "var(--status-warn)",
  grave: "var(--status-danger)",
};

function bucketValue(buckets: DelayBuckets, key: DelayBucketKey): number {
  switch (key) {
    case "puntual":
      return buckets.viajes_bucket_puntual;
    case "leve":
      return buckets.viajes_bucket_leve;
    case "significativo":
      return buckets.viajes_bucket_significativo;
    case "grave":
      return buckets.viajes_bucket_grave;
  }
}

function bucketPct(buckets: DelayBuckets, key: DelayBucketKey): number {
  switch (key) {
    case "puntual":
      return buckets.pct_bucket_puntual;
    case "leve":
      return buckets.pct_bucket_leve;
    case "significativo":
      return buckets.pct_bucket_significativo;
    case "grave":
      return buckets.pct_bucket_grave;
  }
}

export function DonutTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const slice = payload[0]?.payload as Slice | undefined;
  if (!slice) return null;

  return (
    <div className="donut-chart__tooltip glass">
      <span className="donut-chart__tooltip-value">{slice.value} viajes</span>
      <span className="donut-chart__tooltip-label">
        {slice.label} · {slice.pct}%
      </span>
    </div>
  );
}

// Gráfico de tipo queso de los 4 tramos de retraso, compartido por el modal
// de tren, la vista semanal/mensual y la vista global. Los colores de
// estado (--status-ok/mild/warn/danger) no pasan el contraste WCAG 3:1
// completo contra un fondo claro para los tres tramos intermedios/leves
// (verificado con el validador de la skill dataviz) — por eso la leyenda de
// abajo lleva SIEMPRE el valor en texto junto al color, nunca solo el
// color, y cada porción lleva un borde de 2px del color de superficie para
// mantener el borde definido con independencia de ese contraste.
export function DonutChart({ buckets, thresholdMinutes }: DonutChartProps) {
  const slices: Slice[] = DELAY_BUCKET_ORDER.map((key) => ({
    key,
    label: formatDelayBucketLabel(key, thresholdMinutes),
    value: bucketValue(buckets, key),
    pct: bucketPct(buckets, key),
    color: BUCKET_COLOR_VAR[key],
  }));
  const slicesWithData = slices.filter((slice) => slice.value > 0).length;

  return (
    <div className="donut-chart">
      <div className="donut-chart__plot">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={slicesWithData > 1 ? 2 : 0}
              stroke="var(--bg-surface-solid)"
              strokeWidth={2}
              // Sin animación de entrada: cada cambio de tren/periodo
              // seleccionado remonta este componente con un array `data`
              // nuevo, y la animación por defecto de recharts reinicia la
              // transición cada vez — con selecciones rápidas eso deja el
              // gráfico visiblemente "atascado" a medio animar en vez de
              // mostrar de inmediato el estado final.
              isAnimationActive={false}
            >
              {slices.map((slice) => (
                <Cell key={slice.key} fill={slice.color} />
              ))}
            </Pie>
            <Tooltip content={DonutTooltip} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-chart__center" aria-hidden="true">
          <span className="donut-chart__center-value">{buckets.total_viajes}</span>
          <span className="donut-chart__center-label">viajes</span>
        </div>
      </div>

      <ul className="donut-chart__legend">
        {slices.map((slice) => (
          <li key={slice.key} className="donut-chart__legend-item">
            <span className="donut-chart__swatch" style={{ background: slice.color }} aria-hidden="true" />
            <span className="donut-chart__legend-label">{slice.label}</span>
            <span className="donut-chart__legend-value">{slice.pct}%</span>
          </li>
        ))}
      </ul>

      {/* Resumen textual para lectores de pantalla: un gráfico SVG de
          sectores no es accesible por sí solo, y esto además cubre el
          "table view" que la identidad no dependa solo del color. */}
      <p className="sr-only">
        Distribución de {buckets.total_viajes} viajes por tramo de retraso:{" "}
        {slices.map((slice) => `${slice.label}: ${slice.value} viajes (${slice.pct}%)`).join(", ")}.
      </p>
    </div>
  );
}
