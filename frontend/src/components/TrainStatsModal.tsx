import { useEffect } from "react";
import type { TrainMetrics, TrainSchedule } from "../types";
import { formatSpanishDate } from "../utils/metricsFormat";
import { DonutChart } from "./DonutChart";

interface TrainStatsModalProps {
  codComercial: string;
  schedule: TrainSchedule | undefined;
  metrics: TrainMetrics | undefined;
  firstAggregatedDate: string | undefined;
  thresholdMinutes: number | undefined;
  onClose: () => void;
}

// Mismo patrón de interacción que TrainMapModal (backdrop/sheet/grabber/
// Escape), con estadísticas del tren en vez de su posición en vivo.
export function TrainStatsModal({
  codComercial,
  schedule,
  metrics,
  firstAggregatedDate,
  thresholdMinutes,
  onClose,
}: TrainStatsModalProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Estadísticas del tren ${codComercial}`}
      className="modal-backdrop"
      onClick={onClose}
    >
      <div className="modal-sheet glass" onClick={(event) => event.stopPropagation()}>
        <div className="modal-grabber" aria-hidden="true" />
        <div className="modal-header">
          <div>
            <h2 className="modal-title">Tren {codComercial}</h2>
            {schedule && (
              <p className="modal-subtitle">
                <span className="modal-subtitle__item">Salida {schedule.hora_salida}</span>
                <span className="modal-subtitle__item">Llegada {schedule.hora_llegada_destino}</span>
              </p>
            )}
          </div>
          <button type="button" className="icon-btn icon-btn--glass" onClick={onClose} aria-label="Cerrar">
            ✕
          </button>
        </div>

        {metrics ? (
          <div className="train-stats">
            <DonutChart buckets={metrics} thresholdMinutes={thresholdMinutes} />
            <dl className="stats-summary">
              <div className="stats-row">
                <dt>
                  Retrasos significativos acumulados
                  {firstAggregatedDate ? ` desde ${formatSpanishDate(firstAggregatedDate)}` : ""}
                </dt>
                <dd>{metrics.suma_retraso_significativo_minutos} min</dd>
              </div>
              <div className="stats-row">
                <dt>Riesgo de retraso significativo</dt>
                <dd>{metrics.pct_retraso_significativo}%</dd>
              </div>
            </dl>
          </div>
        ) : (
          <p className="state-card">Todavía no hay datos de puntualidad para este tren.</p>
        )}
      </div>
    </div>
  );
}
