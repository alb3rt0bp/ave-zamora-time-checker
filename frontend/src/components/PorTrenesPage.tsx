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

async function loadPageData(): Promise<PageData> {
  const [schedule, trains, global] = await Promise.all([
    fetchTrainSchedule(),
    fetchTrainMetrics(),
    // /metrics/global puede no existir todavía (ningún volcado ejecutado
    // aún): eso no debe impedir que la lista de trenes por día se muestre,
    // solo que el modal no pueda mostrar "desde <fecha>".
    fetchGlobalMetrics().catch((err: unknown) => {
      if (err instanceof NotFoundError) return null;
      throw err;
    }),
  ]);
  return { schedule, trains, global };
}

export function PorTrenesPage() {
  const state = useFetch(loadPageData, []);
  const [openTrainCode, setOpenTrainCode] = useState<string | null>(null);

  return (
    <>
      <header className="app-header glass">
        <h1 className="app-title">Estadísticas · Por trenes</h1>
      </header>
      <main className="app-main">
        {state.status === "loading" && (
          <div className="state-card">
            <span className="spinner" aria-hidden="true" />
            <p>Cargando trenes...</p>
          </div>
        )}
        {(state.status === "error" || state.status === "not-found") && (
          <p role="alert" className="state-card state-card--error">
            No se han podido cargar los trenes.
          </p>
        )}
        {state.status === "ok" && (
          <PorTrenesList
            schedule={state.data.schedule}
            trains={state.data.trains}
            global={state.data.global}
            onSelectTrain={setOpenTrainCode}
          />
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

interface PorTrenesListProps {
  schedule: TrainSchedule[];
  trains: TrainMetrics[];
  global: GlobalMetrics | null;
  onSelectTrain: (codComercial: string) => void;
}

function PorTrenesList({ schedule, onSelectTrain }: PorTrenesListProps) {
  if (schedule.length === 0) {
    return <p className="state-card">No hay trenes en el horario.</p>;
  }

  const groups = groupByWeekdayGroup(schedule);

  return (
    <div className="weekday-groups">
      {WEEKDAY_GROUPS.filter((group) => (groups.get(group.key) ?? []).length > 0).map((group) => (
        <section key={group.key} className="weekday-group">
          <h2 className="weekday-group__title">{group.label}</h2>
          <div className="weekday-group__trains">
            {(groups.get(group.key) ?? []).map((train) => (
              <button
                key={train.cod_comercial}
                type="button"
                className="weekday-group__chip"
                onClick={() => onSelectTrain(train.cod_comercial)}
              >
                {`${train.cod_comercial} · ${train.sentido}`}
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
