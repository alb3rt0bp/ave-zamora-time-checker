import { useState } from "react";
import { fetchMonthMetrics, fetchWeekMetrics } from "../api";
import type { DelayBuckets, MonthMetrics, WeekMetrics } from "../types";
import { useFetch } from "../hooks/useFetch";
import { formatMonthName, formatShortDate } from "../utils/metricsFormat";
import { DonutChart } from "./DonutChart";

type Mode = "semanas" | "meses";

interface PageData {
  weeks: WeekMetrics[];
  months: MonthMetrics[];
}

async function loadPageData(): Promise<PageData> {
  const [weeks, months] = await Promise.all([fetchWeekMetrics(), fetchMonthMetrics()]);
  return { weeks, months };
}

export function weekKey(week: WeekMetrics): string {
  return `${week.iso_year}-W${week.iso_week}`;
}

export function weekLabel(week: WeekMetrics): string {
  const label = `${formatShortDate(week.week_start)} - ${formatShortDate(week.week_end)} de ${week.iso_year}`;
  return week.is_complete ? label : `${label} (en curso)`;
}

function monthKey(month: MonthMetrics): string {
  return `${month.year}-${month.month}`;
}

function monthLabel(month: MonthMetrics): string {
  const label = `${formatMonthName(month.month)} de ${month.year}`;
  return month.is_complete ? label : `${label} (en curso)`;
}

export function PorTiemposPage() {
  const state = useFetch(loadPageData, []);
  const [mode, setMode] = useState<Mode>("semanas");

  return (
    <>
      <header className="app-header glass">
        <h1 className="app-title">Estadísticas · Por intervalos</h1>
        <div className="segmented-control glass">
          <button
            type="button"
            className={`segmented-control__option${mode === "semanas" ? " segmented-control__option--active" : ""}`}
            aria-pressed={mode === "semanas"}
            onClick={() => setMode("semanas")}
          >
            Semanas
          </button>
          <button
            type="button"
            className={`segmented-control__option${mode === "meses" ? " segmented-control__option--active" : ""}`}
            aria-pressed={mode === "meses"}
            onClick={() => setMode("meses")}
          >
            Meses
          </button>
        </div>
      </header>
      <main className="app-main">
        {state.status === "loading" && (
          <div className="state-card">
            <span className="spinner" aria-hidden="true" />
            <p>Cargando periodos...</p>
          </div>
        )}
        {(state.status === "error" || state.status === "not-found") && (
          <p role="alert" className="state-card state-card--error">
            No se han podido cargar los periodos.
          </p>
        )}
        {state.status === "ok" && mode === "semanas" && (
          <PeriodSection
            periods={state.data.weeks}
            getKey={weekKey}
            getLabel={weekLabel}
            selectLabel="Selecciona una semana"
            emptyMessage="Todavía no hay datos de ninguna semana."
          />
        )}
        {state.status === "ok" && mode === "meses" && (
          <PeriodSection
            periods={state.data.months}
            getKey={monthKey}
            getLabel={monthLabel}
            selectLabel="Selecciona un mes"
            emptyMessage="Todavía no hay datos de ningún mes."
          />
        )}
      </main>
    </>
  );
}

interface PeriodSectionProps<T extends DelayBuckets> {
  periods: T[];
  getKey: (period: T) => string;
  getLabel: (period: T) => string;
  selectLabel: string;
  emptyMessage: string;
}

export function PeriodSection<T extends DelayBuckets>({
  periods,
  getKey,
  getLabel,
  selectLabel,
  emptyMessage,
}: PeriodSectionProps<T>) {
  // Por defecto, el periodo completo más reciente (las listas ya vienen
  // ordenadas ascendentemente desde el API).
  const [selectedKey, setSelectedKey] = useState(() => (periods.length > 0 ? getKey(periods[periods.length - 1]) : ""));

  if (periods.length === 0) {
    return <p className="state-card">{emptyMessage}</p>;
  }

  const selected = periods.find((period) => getKey(period) === selectedKey) ?? periods[periods.length - 1];

  return (
    <div>
      <label className="period-select-label" htmlFor="period-select">
        {selectLabel}
      </label>
      <select
        id="period-select"
        className="period-select"
        value={getKey(selected)}
        onChange={(event) => setSelectedKey(event.target.value)}
      >
        {periods.map((period) => (
          <option key={getKey(period)} value={getKey(period)}>
            {getLabel(period)}
          </option>
        ))}
      </select>

      <div className="train-stats">
        <DonutChart buckets={selected} />
        <dl className="stats-summary">
          <div className="stats-row">
            <dt>Retrasos significativos acumulados</dt>
            <dd>{selected.suma_retraso_significativo_minutos} min</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
