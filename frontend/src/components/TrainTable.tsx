import { useState } from "react";
import type { RenfeTren, TrainRow } from "../types";
import { CLAIM_THRESHOLD_MIN, delayStatus, formatDelay } from "../utils/trainFormat";
import { MapPinIcon } from "./icons";
import { TrainMapModal } from "./TrainMapModal";

interface TrainTableProps {
  rows: TrainRow[];
  flota?: Map<string, RenfeTren>;
}

const POSSIBLE_CLAIM_THRESHOLD_MIN = 60;
const CLAIM_URL = "https://venta.renfe.com/vol/petitionPersonalData.do?petition_personal_data_origin=CLAIM";

const POSSIBLE_CLAIM_URL = "https://www.renfe.com/es/es/ayuda/compromiso-puntualidad";

function openInNewTab(url: string) {
  window.open(url, "_blank", "noopener,noreferrer");
}

export function TrainTable({ rows, flota = new Map() }: TrainTableProps) {
  const [openTrainCode, setOpenTrainCode] = useState<string | null>(null);

  if (rows.length === 0) {
    return <p className="state-card">No hay trenes para mostrar.</p>;
  }

  const sortedRows = [...rows].sort((a, b) => a.horaProgramada.localeCompare(b.horaProgramada));

  return (
    <>
      <div className="table-card glass">
        <div className="table-scroll">
          <table className="train-table">
            <thead>
              <tr>
                <th>Tren</th>
                <th>Sentido</th>
                <th>Hora programada</th>
                <th>Hora de llegada corregida</th>
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

                return (
                  <tr key={row.codComercial}>
                    <td>
                      {flota.has(row.codComercial) ? (
                        <button
                          type="button"
                          className="train-chip"
                          onClick={() => setOpenTrainCode(row.codComercial)}
                        >
                          <MapPinIcon />
                          {row.codComercial}
                        </button>
                      ) : (
                        <span className="cell-primary">{row.codComercial}</span>
                      )}
                    </td>
                    <td>
                      <span className="sentido-badge">{row.sentido}</span>
                    </td>
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
      {openTrainCode && (
        <TrainMapModal codComercial={openTrainCode} flota={flota} onClose={() => setOpenTrainCode(null)} />
      )}
    </>
  );
}
