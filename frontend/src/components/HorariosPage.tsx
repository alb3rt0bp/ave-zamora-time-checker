import { fetchTrainSchedule } from "../api";
import type { TrainSchedule } from "../types";
import { useFetch } from "../hooks/useFetch";
import { WEEKDAY_GROUPS, groupByWeekdayGroup } from "../utils/weekdayGroups";

export function HorariosPage() {
  const state = useFetch(fetchTrainSchedule, []);

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
        {state.status === "ok" && <HorariosList schedule={state.data} />}
      </main>
    </>
  );
}

interface HorariosListProps {
  schedule: TrainSchedule[];
}

function HorariosList({ schedule }: HorariosListProps) {
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
                        <span className="cell-primary">{train.cod_comercial}</span>
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
