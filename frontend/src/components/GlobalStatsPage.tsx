import { useState } from "react";
import { fetchGlobalMetrics, fetchTrainSchedule } from "../api";
import type { GlobalMetrics, TrainSchedule } from "../types";
import { useFetch } from "../hooks/useFetch";
import { formatFranjaHoraria, formatSpanishDate, formatWeekday } from "../utils/metricsFormat";
import { DonutChart } from "./DonutChart";
import { TrainStatsModal } from "./TrainStatsModal";

interface PageData {
  global: GlobalMetrics;
  schedule: TrainSchedule[];
}

async function loadPageData(): Promise<PageData> {
  const [global, schedule] = await Promise.all([fetchGlobalMetrics(), fetchTrainSchedule()]);
  return { global, schedule };
}

export function GlobalStatsPage() {
  const state = useFetch(loadPageData, []);
  const [openTrainCode, setOpenTrainCode] = useState<string | null>(null);

  return (
    <>
      <header className="app-header glass">
        <h1 className="app-title">Estadísticas · Global</h1>
      </header>
      <main className="app-main">
        {state.status === "loading" && (
          <div className="state-card">
            <span className="spinner" aria-hidden="true" />
            <p>Cargando estadísticas globales...</p>
          </div>
        )}
        {state.status === "not-found" && (
          <p className="state-card">Todavía no hay datos suficientes para las estadísticas globales.</p>
        )}
        {state.status === "error" && (
          <p role="alert" className="state-card state-card--error">
            No se han podido cargar las estadísticas globales.
          </p>
        )}
        {state.status === "ok" && <GlobalStatsContent global={state.data.global} onSelectTrain={setOpenTrainCode} />}
      </main>
      {openTrainCode && state.status === "ok" && (
        <TrainStatsModal
          codComercial={openTrainCode}
          schedule={state.data.schedule.find((train) => train.cod_comercial === openTrainCode)}
          metrics={
            [state.data.global.tren_mas_probable, state.data.global.tren_menos_probable].find(
              (train) => train?.cod_comercial === openTrainCode,
            ) ?? undefined
          }
          firstAggregatedDate={state.data.global.first_aggregated_date}
          thresholdMinutes={state.data.global.significant_delay_threshold_minutes}
          onClose={() => setOpenTrainCode(null)}
        />
      )}
    </>
  );
}

function GlobalStatsContent({
  global,
  onSelectTrain,
}: {
  global: GlobalMetrics;
  onSelectTrain: (codComercial: string) => void;
}) {
  return (
    <div className="train-stats">
      <DonutChart buckets={global} thresholdMinutes={global.significant_delay_threshold_minutes} />
      <dl className="stats-summary">
        <div className="stats-row">
          <dt>Retrasos significativos acumulados desde {formatSpanishDate(global.first_aggregated_date)}</dt>
          <dd>{global.suma_retraso_significativo_minutos} min</dd>
        </div>
        {global.dia_semana_mas_probable && (
          <div className="stats-row">
            <dt>Día con más riesgo de retraso significativo</dt>
            <dd>{formatWeekday(global.dia_semana_mas_probable.dia_semana)}</dd>
          </div>
        )}
        {global.dia_semana_menos_probable && (
          <div className="stats-row">
            <dt>Día con menos riesgo de retraso significativo</dt>
            <dd>{formatWeekday(global.dia_semana_menos_probable.dia_semana)}</dd>
          </div>
        )}
        {global.franja_horaria_mas_probable && (
          <div className="stats-row">
            <dt>Franja horaria con más riesgo de retraso significativo</dt>
            <dd>{formatFranjaHoraria(global.franja_horaria_mas_probable.franja)}</dd>
          </div>
        )}
        {global.tren_mas_probable && (
          <div className="stats-row">
            <dt>Tren con más riesgo de retraso significativo</dt>
            <dd>
              <button
                type="button"
                className="stats-row__link"
                onClick={() => onSelectTrain(global.tren_mas_probable!.cod_comercial)}
              >
                {global.tren_mas_probable.cod_comercial}
              </button>
            </dd>
          </div>
        )}
        {global.tren_menos_probable && (
          <div className="stats-row">
            <dt>Tren con menos riesgo de retraso significativo</dt>
            <dd>
              <button
                type="button"
                className="stats-row__link"
                onClick={() => onSelectTrain(global.tren_menos_probable!.cod_comercial)}
              >
                {global.tren_menos_probable.cod_comercial}
              </button>
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}
