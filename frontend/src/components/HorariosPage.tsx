import { useState } from "react";
import { fetchGlobalMetrics, fetchTrainMetrics, fetchTrainSchedule, NotFoundError } from "../api";
import type { GlobalMetrics, TrainMetrics, TrainSchedule } from "../types";
import { useFetch } from "../hooks/useFetch";
import { WEEKDAY_GROUPS, groupByWeekdayGroup } from "../utils/weekdayGroups";
import { TrainStatsModal } from "./TrainStatsModal";

interface PageData {
  schedule: TrainSchedule[];
  trains: TrainMetrics[];
  global: GlobalMetrics | null;
}

// Mismo patrón que PorTrenesPage.tsx: /metrics/global puede no existir
// todavía (ningún volcado ejecutado aún), eso no debe impedir mostrar el
// horario, solo que el modal de detalle no pueda mostrar "desde <fecha>".
async function loadPageData(): Promise<PageData> {
  const [schedule, trains, global] = await Promise.all([
    fetchTrainSchedule(),
    fetchTrainMetrics(),
    fetchGlobalMetrics().catch((err: unknown) => {
      if (err instanceof NotFoundError) return null;
      throw err;
    }),
  ]);
  return { schedule, trains, global };
}

export function HorariosPage() {
  const state = useFetch(loadPageData, []);
  const [openTrainCode, setOpenTrainCode] = useState<string | null>(null);

  return (
    <>
      <header className="app-header glass">
        <h1 className="app-title">Horarios de trenes AVE</h1>
      </header>
      <main className="app-main">
        {state.status === "loading" && (
          <div className="state-card">
            <span className="spinner" aria-hidden="true" />
            <p>Cargando horarios...</p>
          </div>
        )}
        {(state.status === "error" || state.status === "not-found") && (
          <p role="alert" className="state-card state-card--error">
            No se han podido cargar los horarios.
          </p>
        )}
        {state.status === "ok" && (
          <HorariosList schedule={state.data.schedule} onSelectTrain={setOpenTrainCode} />
        )}
      </main>
      {openTrainCode && state.status === "ok" && (
        <TrainStatsModal
          codComercial={openTrainCode}
          schedule={state.data.schedule.find((train) => train.cod_comercial === openTrainCode)}
          metrics={state.data.trains.find((train) => train.cod_comercial === openTrainCode)}
          firstAggregatedDate={state.data.global?.first_aggregated_date}
          thresholdMinutes={state.data.global?.significant_delay_threshold_minutes}
          onClose={() => setOpenTrainCode(null)}
        />
      )}
    </>
  );
}

interface HorariosListProps {
  schedule: TrainSchedule[];
  onSelectTrain: (codComercial: string) => void;
}

function HorariosList({ schedule, onSelectTrain }: HorariosListProps) {
  if (schedule.length === 0) {
    return <p className="state-card">No hay trenes en el horario.</p>;
  }

  const groups = groupByWeekdayGroup(schedule);
  const visibleGroups = WEEKDAY_GROUPS.map((group) => ({ group, trains: groups.get(group.key) ?? [] })).filter(
    ({ trains }) => trains.length > 0,
  );

  return (
    <div className="weekday-groups">
      {visibleGroups.map(({ group, trains }) => (
        <section key={group.key} className="weekday-group">
          <h2 className="weekday-group__title">{group.label}</h2>
          <div className="table-card glass">
            <div className="table-scroll">
              <table className="train-table">
                <thead>
                  <tr>
                    <th>Tren</th>
                    <th>Sentido</th>
                    <th>Hora de salida</th>
                    <th>Hora de llegada</th>
                  </tr>
                </thead>
                <tbody>
                  {trains.map((train) => (
                    <tr key={train.cod_comercial}>
                      <td>
                        <button
                          type="button"
                          className="train-chip train-chip--detalle"
                          title={`Ver el detalle del tren ${train.cod_comercial}`}
                          onClick={() => onSelectTrain(train.cod_comercial)}
                        >
                          {train.cod_comercial}
                        </button>
                      </td>
                      <td>
                        <span className="sentido-badge">{train.sentido}</span>
                      </td>
                      <td>{train.hora_salida}</td>
                      <td>{train.hora_llegada_destino}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
