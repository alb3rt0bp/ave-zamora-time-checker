import type { TrainRow } from "../types";
import { formatDelay } from "../utils/trainFormat";

interface TrainTableProps {
  rows: TrainRow[];
}

export function TrainTable({ rows }: TrainTableProps) {
  if (rows.length === 0) {
    return <p>No hay trenes para mostrar.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Tren</th>
          <th>Sentido</th>
          <th>Hora programada</th>
          <th>Hora llegada</th>
          <th>Retraso</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.codComercial}>
            <td>{row.codComercial}</td>
            <td>{row.sentido}</td>
            <td>{row.horaProgramada}</td>
            <td>{row.cancelado ? "Cancelado" : (row.horaLlegada ?? "-")}</td>
            <td>{row.cancelado ? "-" : formatDelay(row.retrasoMinutos)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
