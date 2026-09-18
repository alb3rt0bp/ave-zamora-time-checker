import { useEffect } from "react";
import type { ReactNode } from "react";
import type { DelayEstimate, TrainMetrics, TrainSchedule } from "../types";
import { addMinutesToTime } from "../utils/delayEstimate";
import { formatSpanishDate } from "../utils/metricsFormat";
import { formatDelay } from "../utils/trainFormat";
import { DonutChart } from "./DonutChart";

interface TrainStatsModalProps {
  codComercial: string;
  schedule: TrainSchedule | undefined;
  metrics: TrainMetrics | undefined;
  firstAggregatedDate: string | undefined;
  thresholdMinutes: number | undefined;
  onClose: () => void;
}

interface ArrivalEstimateProps {
  estimate: DelayEstimate;
  horaLlegadaDestino: string;
  sentido: string;
  firstAggregatedDate: string | undefined;
}

// La estimación se aplica SIEMPRE a la hora de llegada, nunca a la de
// salida: minutos_retraso se mide en el extremo que este sistema sigue de
// cada sentido (Chamartín para Madrid, Zamora para Galicia), que es
// justamente hora_llegada_destino. El retraso en la salida es otra variable
// distinta (para los trenes a Madrid, menor: acumulan minutos después de
// pasar por Zamora) y no se estima aquí.
function ArrivalEstimate({
  estimate,
  horaLlegadaDestino,
  sentido,
  firstAggregatedDate,
}: ArrivalEstimateProps) {
  const probable = addMinutesToTime(horaLlegadaDestino, estimate.mediana_minutos);
  const habitualDesde = addMinutesToTime(horaLlegadaDestino, estimate.p25_minutos);
  const habitualHasta = addMinutesToTime(horaLlegadaDestino, estimate.p75_minutos);
  const excepcional = addMinutesToTime(horaLlegadaDestino, estimate.p90_minutos);

  return (
    <section className="arrival-estimate">
      <h3 className="arrival-estimate__label">Llegada probable</h3>
      <p className="arrival-estimate__headline">
        <span className="arrival-estimate__time">{probable}</span>
        <span className="arrival-estimate__delta">{formatDelay(estimate.mediana_minutos)}</span>
      </p>
      <p className="arrival-estimate__spread">
        La mitad de los viajes llegan entre las {habitualDesde} y las {habitualHasta}.
        {" "}
        Uno de cada diez llega más tarde de las {excepcional}.
      </p>
      <p className="arrival-estimate__basis">
        {estimate.base === "tren" ? (
          <>
            Sobre {estimate.viajes_estimacion} viajes de este tren
            {firstAggregatedDate ? ` desde ${formatSpanishDate(firstAggregatedDate)}` : ""}.
          </>
        ) : (
          <>
            Este tren todavía no tiene viajes suficientes para una estimación propia: se
            muestra la de los {estimate.viajes_estimacion} viajes registrados en sentido{" "}
            {sentido}.
          </>
        )}
      </p>
    </section>
  );
}

export interface TrainStatsFaceProps {
  codComercial: string;
  schedule: TrainSchedule | undefined;
  metrics: TrainMetrics | undefined;
  firstAggregatedDate: string | undefined;
  thresholdMinutes: number | undefined;
  // Acciones de la cabecera (volteo + cerrar en TrainLiveModal, solo cerrar
  // en el TrainStatsModal independiente de más abajo).
  headerActions: ReactNode;
}

// Contenido de la cara "detalle": cabecera + estadísticas, sin el
// backdrop/sheet/grabber que lo envuelve, para poder reutilizarlo dentro de
// TrainLiveModal (ver TrainMapModal.tsx) además de en el TrainStatsModal
// independiente de abajo.
export function TrainStatsFace({
  codComercial,
  schedule,
  metrics,
  firstAggregatedDate,
  thresholdMinutes,
  headerActions,
}: TrainStatsFaceProps) {
  const estimate = metrics?.estimacion_retraso ?? null;

  return (
    <>
      <div className="modal-header">
        <div>
          <h2 className="modal-title">Tren {codComercial}</h2>
          {schedule && (
            <p className="modal-subtitle">
              <span className="modal-subtitle__item">Salida {schedule.hora_salida}</span>
              <span className="modal-subtitle__item">
                Llegada {schedule.hora_llegada_destino}
                {estimate && (
                  <span className="modal-subtitle__delta">{formatDelay(estimate.mediana_minutos)}</span>
                )}
              </span>
            </p>
          )}
        </div>
        {headerActions}
      </div>

      {metrics ? (
        <div className="train-stats">
          {estimate && schedule && (
            <ArrivalEstimate
              estimate={estimate}
              horaLlegadaDestino={schedule.hora_llegada_destino}
              sentido={metrics.sentido}
              firstAggregatedDate={firstAggregatedDate}
            />
          )}
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
    </>
  );
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
        <TrainStatsFace
          codComercial={codComercial}
          schedule={schedule}
          metrics={metrics}
          firstAggregatedDate={firstAggregatedDate}
          thresholdMinutes={thresholdMinutes}
          headerActions={
            <button type="button" className="icon-btn icon-btn--glass" onClick={onClose} aria-label="Cerrar">
              ✕
            </button>
          }
        />
      </div>
    </div>
  );
}
