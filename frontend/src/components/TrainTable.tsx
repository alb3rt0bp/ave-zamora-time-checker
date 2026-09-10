import { useState } from "react";
import type { GlobalMetrics, RenfeTren, TrainMetrics, TrainRow, TrainSchedule } from "../types";
import { CLAIM_THRESHOLD_MIN, delayStatus, formatDelay } from "../utils/trainFormat";
import { MapPinIcon } from "./icons";
import { TrainMapModal } from "./TrainMapModal";
import { TrainStatsModal } from "./TrainStatsModal";

interface TrainTableProps {
  rows: TrainRow[];
  // Solo la vista de hoy pasa flota: la posición en vivo de un tren con ese
  // mismo codComercial no dice nada del viaje de un día pasado, así que en
  // los días volcados el código de tren abre siempre el detalle estadístico.
  flota?: Map<string, RenfeTren>;
  schedule?: Map<string, TrainSchedule>;
  metrics?: Map<string, TrainMetrics>;
  globalMetrics?: GlobalMetrics | null;
}

// Qué abre el código de tren de cada fila: el mapa en vivo cuando hay
// posición real (solo hoy), y si no el detalle del tren. La modalidad se fija
// al pulsar y no se recalcula: si el tren desaparece de flotaLD.json en el
// siguiente sondeo de 15s, el mapa ya abierto no debe convertirse en otra
// modal bajo el dedo del usuario.
interface OpenModal {
  codComercial: string;
  kind: "mapa" | "detalle";
}

const POSSIBLE_CLAIM_THRESHOLD_MIN = 60;
const CLAIM_URL = "https://venta.renfe.com/vol/petitionPersonalData.do?petition_personal_data_origin=CLAIM";

const POSSIBLE_CLAIM_URL = "https://www.renfe.com/es/es/ayuda/compromiso-puntualidad";

function openInNewTab(url: string) {
  window.open(url, "_blank", "noopener,noreferrer");
}

export function TrainTable({
  rows,
  flota = new Map(),
  schedule = new Map(),
  metrics = new Map(),
  globalMetrics = null,
}: TrainTableProps) {
  const [openModal, setOpenModal] = useState<OpenModal | null>(null);

  if (rows.length === 0) {
    return <p className="state-card">No hay trenes para mostrar.</p>;
  }

  const sortedRows = [...rows].sort((a, b) => a.horaProgramada.localeCompare(b.horaProgramada));
  const openRow = openModal ? sortedRows.find((row) => row.codComercial === openModal.codComercial) : undefined;

  return (
    <>
      <div className="table-card glass">
        <div className="table-scroll">
          <table className="train-table">
            <thead>
              <tr>
                <th>Tren</th>
                <th>Sentido</th>
                <th>Hora de salida</th>
                <th>Hora de llegada</th>
                <th>Llegada corregida</th>
                <th>Retraso</th>
                {/* Última columna a propósito: en móvil es la única que puede
                    quedar fuera de la vista inicial y requerir scroll
                    horizontal, ya que el resto de datos son más críticos. */}
                <th>Hora de paso por Zamora</th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => {
                const status = delayStatus(row.retrasoMinutos, row.cancelado);
                const showClaim = !row.cancelado && row.retrasoMinutos !== null && row.retrasoMinutos > CLAIM_THRESHOLD_MIN;
                const showPossibleClaim = showClaim && (row.retrasoMinutos as number) > POSSIBLE_CLAIM_THRESHOLD_MIN;
                const horaSalida = schedule.get(row.codComercial)?.hora_salida ?? null;
                const enVivo = flota.has(row.codComercial);

                return (
                  <tr key={row.codComercial}>
                    <td>
                      <button
                        type="button"
                        className={enVivo ? "train-chip" : "train-chip train-chip--detalle"}
                        title={
                          enVivo
                            ? `Ver la posición en vivo del tren ${row.codComercial}`
                            : `Ver el detalle del tren ${row.codComercial}`
                        }
                        onClick={() =>
                          setOpenModal({
                            codComercial: row.codComercial,
                            kind: enVivo ? "mapa" : "detalle",
                          })
                        }
                      >
                        {enVivo && <MapPinIcon />}
                        {row.codComercial}
                      </button>
                    </td>
                    <td>
                      <span className="sentido-badge">{row.sentido}</span>
                    </td>
                    <td>{horaSalida ?? "-"}</td>
                    <td>{row.horaProgramada}</td>
                    <td>
                      {row.cancelado ? (
                        <span className="status-pill status-pill--danger">Cancelado</span>
                      ) : (
                        (row.horaLlegada ?? "-")
                      )}
                    </td>
                    <td>
                      {row.cancelado ? (
                        "-"
                      ) : (
                        <>
                          <span className={`status-pill status-pill--${status}`}>
                            {formatDelay(row.retrasoMinutos)}
                          </span>
                          {showClaim && (
                            <div className="claim-actions">
                              <button type="button" className="claim-btn" onClick={() => openInNewTab(CLAIM_URL)}>
                                📝 Reclamar
                              </button>
                              {showPossibleClaim && (
                                <button
                                  type="button"
                                  className="claim-btn"
                                  onClick={() => openInNewTab(POSSIBLE_CLAIM_URL)}
                                >
                                  💶 Posible indemnización
                                </button>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </td>
                    <td>{row.cancelado ? "-" : (row.horaPasoZamora ?? "-")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      {openModal?.kind === "mapa" && openRow && (
        <TrainMapModal
          codComercial={openRow.codComercial}
          sentido={openRow.sentido}
          horaSalida={schedule.get(openRow.codComercial)?.hora_salida ?? null}
          horaLlegada={openRow.horaProgramada}
          retrasoMinutos={openRow.retrasoMinutos}
          cancelado={openRow.cancelado}
          flota={flota}
          onClose={() => setOpenModal(null)}
        />
      )}
      {openModal?.kind === "detalle" && (
        <TrainStatsModal
          codComercial={openModal.codComercial}
          schedule={schedule.get(openModal.codComercial)}
          metrics={metrics.get(openModal.codComercial)}
          firstAggregatedDate={globalMetrics?.first_aggregated_date}
          thresholdMinutes={globalMetrics?.significant_delay_threshold_minutes}
          onClose={() => setOpenModal(null)}
        />
      )}
    </>
  );
}
