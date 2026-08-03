import type { TrainRow } from "../types";
import { formatDelay } from "../utils/trainFormat";

interface TrainTableProps {
  rows: TrainRow[];
}

const cellStyle = { border: "1px solid #ccc" };

const CLAIM_THRESHOLD_MIN = 15;
const CLAIM_URL = "https://venta.renfe.com/vol/petitionPersonalData.do?petition_personal_data_origin=CLAIM";

const POSSIBLE_CLAIM_THRESHOLD_MIN = 60;
const POSSIBLE_CLAIM_URL = "https://www.renfe.com/es/es/ayuda/compromiso-puntualidad";

function openInNewTab(url: string) {
  window.open(url, "_blank", "noopener,noreferrer");
}

export function TrainTable({ rows }: TrainTableProps) {
  if (rows.length === 0) {
    return <p>No hay trenes para mostrar.</p>;
  }

  const sortedRows = [...rows].sort((a, b) => a.horaProgramada.localeCompare(b.horaProgramada));

  return (
    <table style={{ borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={cellStyle}>Tren</th>
          <th style={cellStyle}>Sentido</th>
          <th style={cellStyle}>Hora programada</th>
          <th style={cellStyle}>Hora de paso por Zamora</th>
          <th style={cellStyle}>Hora de llegada corregida</th>
          <th style={cellStyle}>Retraso</th>
        </tr>
      </thead>
      <tbody>
        {sortedRows.map((row) => (
          <tr key={row.codComercial}>
            <td style={cellStyle}>{row.codComercial}</td>
            <td style={cellStyle}>{row.sentido}</td>
            <td style={cellStyle}>{row.horaProgramada}</td>
            <td style={cellStyle}>{row.cancelado ? "-" : (row.horaPasoZamora ?? "-")}</td>
            <td style={cellStyle}>{row.cancelado ? "Cancelado" : (row.horaLlegada ?? "-")}</td>
            <td style={cellStyle}>
              {row.cancelado ? (
                "-"
              ) : (
                <>
                  {formatDelay(row.retrasoMinutos)}
                  {row.retrasoMinutos !== null && row.retrasoMinutos > CLAIM_THRESHOLD_MIN && (
                    <button type="button" onClick={() => openInNewTab(CLAIM_URL)}>
                      📝 Reclamar
                    </button>
                  )}
                  {row.retrasoMinutos !== null && row.retrasoMinutos > POSSIBLE_CLAIM_THRESHOLD_MIN && (
                    <button type="button" onClick={() => openInNewTab(POSSIBLE_CLAIM_URL)}>
                      💶 Posible indemnización
                    </button>
                  )}
                </>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
