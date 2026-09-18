import { useEffect, useRef, useState } from "react";
import type { RenfeTren, TrainMetrics, TrainSchedule } from "../types";
import { FlipIcon } from "./icons";
import { TrainMapFace } from "./TrainMapModal";
import { TrainStatsFace } from "./TrainStatsModal";

// Velocidad "media-rápida" pedida para el volteo: lo bastante visible para
// leerse como una animación intencionada, sin retrasar la apertura del
// detalle. El contenido se intercambia a mitad de camino (FLIP_SWAP_MS),
// momento en el que la tarjeta está de perfil (rotateY 90deg) y por tanto
// invisible, así el cambio de cara no se ve como un corte brusco.
const FLIP_DURATION_MS = 320;
const FLIP_SWAP_MS = FLIP_DURATION_MS / 2;

type FaceView = "mapa" | "detalle";

interface TrainLiveModalProps {
  codComercial: string;
  sentido: string;
  horaSalida: string | null;
  horaLlegada: string | null;
  retrasoMinutos: number | null;
  cancelado: boolean;
  flota: Map<string, RenfeTren>;
  schedule: TrainSchedule | undefined;
  metrics: TrainMetrics | undefined;
  firstAggregatedDate: string | undefined;
  thresholdMinutes: number | undefined;
  onClose: () => void;
}

// Modal con volteo para trenes con posición en vivo: una misma hoja que
// alterna entre la cara "mapa" (TrainMapFace) y la cara "detalle"
// (TrainStatsFace) girando sobre sí misma, en vez de sustituir una modal
// entera por otra (ver TrainTable.tsx, que sigue abriendo TrainStatsModal
// directamente para trenes sin posición en vivo, sin botón de volteo porque
// no hay mapa al que volver).
export function TrainLiveModal({
  codComercial,
  sentido,
  horaSalida,
  horaLlegada,
  retrasoMinutos,
  cancelado,
  flota,
  schedule,
  metrics,
  firstAggregatedDate,
  thresholdMinutes,
  onClose,
}: TrainLiveModalProps) {
  const [view, setView] = useState<FaceView>("mapa");
  const [isFlipping, setIsFlipping] = useState(false);
  const swapTimeoutRef = useRef<number | undefined>(undefined);
  const endTimeoutRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(
    () => () => {
      window.clearTimeout(swapTimeoutRef.current);
      window.clearTimeout(endTimeoutRef.current);
    },
    [],
  );

  function handleFlip() {
    if (isFlipping) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      setView((current) => (current === "mapa" ? "detalle" : "mapa"));
      return;
    }

    setIsFlipping(true);
    swapTimeoutRef.current = window.setTimeout(() => {
      setView((current) => (current === "mapa" ? "detalle" : "mapa"));
    }, FLIP_SWAP_MS);
    endTimeoutRef.current = window.setTimeout(() => {
      setIsFlipping(false);
    }, FLIP_DURATION_MS);
  }

  const train = flota.get(codComercial);
  // El tren pudo desaparecer de la flota (p.ej. llegó a destino) mientras la
  // cara "mapa" estaba abierta; ahí ya no hay una posición que mostrar (igual
  // que TrainMapModal). Si el usuario ya había volteado al detalle, ese sigue
  // funcionando sin datos en vivo, así que no cerramos la modal por eso.
  if (view === "mapa" && !train) return null;

  const flipButton = (
    <button
      type="button"
      className="icon-btn icon-btn--glass"
      onClick={handleFlip}
      disabled={isFlipping}
      aria-label={view === "mapa" ? "Ver el detalle del tren" : "Ver la posición en el mapa"}
      title={view === "mapa" ? "Ver el detalle del tren" : "Ver la posición en el mapa"}
    >
      <FlipIcon />
    </button>
  );
  const closeButton = (
    <button type="button" className="icon-btn icon-btn--glass" onClick={onClose} aria-label="Cerrar">
      ✕
    </button>
  );
  const headerActions = (
    <div className="modal-header__actions">
      {flipButton}
      {closeButton}
    </div>
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Tren ${codComercial}`}
      className="modal-backdrop modal-backdrop--flip"
      onClick={onClose}
    >
      <div
        className={`modal-sheet glass flip-card${isFlipping ? " flip-card--flipping" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-grabber" aria-hidden="true" />
        {view === "mapa" ? (
          <TrainMapFace
            codComercial={codComercial}
            sentido={sentido}
            horaSalida={horaSalida}
            horaLlegada={horaLlegada}
            retrasoMinutos={retrasoMinutos}
            cancelado={cancelado}
            train={train}
            headerActions={headerActions}
          />
        ) : (
          <TrainStatsFace
            codComercial={codComercial}
            schedule={schedule}
            metrics={metrics}
            firstAggregatedDate={firstAggregatedDate}
            thresholdMinutes={thresholdMinutes}
            headerActions={headerActions}
          />
        )}
      </div>
    </div>
  );
}
