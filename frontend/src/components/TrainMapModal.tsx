import { useEffect, useMemo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import type { RenfeTren } from "../types";
import { computeZoomForScale } from "../utils/mapScale";
import { delayStatus, formatDelay } from "../utils/trainFormat";

const SPAIN_CENTER: [number, number] = [40.4168, -3.7038];
const SPAIN_ZOOM = 6;

// Emoji de tren de alta velocidad: en Apple/Twemoji/Noto la punta (el
// morro) queda a la izquierda por defecto, que es la orientación natural
// para sentido Galicia (al oeste de Zamora/Madrid en cualquier mapa
// orientado al norte); para sentido Madrid (al este) se refleja en CSS
// (ver .train-marker-icon__glyph--right en index.css).
const TRAIN_GLYPH = "🚄";

function createTrainIcon(sentido: string): L.DivIcon {
  const pointingRight = sentido === "Madrid";
  const glyphClass = `train-marker-icon__glyph${pointingRight ? " train-marker-icon__glyph--right" : ""}`;
  return L.divIcon({
    className: "train-marker-icon",
    html: `<span class="${glyphClass}" aria-hidden="true">${TRAIN_GLYPH}</span>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

interface FlyToTrainProps {
  position: [number, number];
  zoom: number;
}

// Anima el mapa, nada más montar la modal, desde la vista general de España
// (ver SPAIN_CENTER/SPAIN_ZOOM en MapContainer) hasta encuadrar el tren a la
// escala pedida (1 cm en pantalla = 5 km reales, ver computeZoomForScale).
function FlyToTrain({ position, zoom }: FlyToTrainProps) {
  const map = useMap();

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    map.flyTo(position, zoom, { duration: prefersReducedMotion ? 0 : 1.5 });
    // Solo al montar: si el tren se mueve mientras la modal está abierta, el
    // Marker sigue la nueva posición (ver más abajo), pero no repetimos la
    // animación de acercamiento inicial en cada refresco de flota.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}

interface TrainMapModalProps {
  codComercial: string;
  sentido: string;
  horaSalida: string | null;
  horaLlegada: string | null;
  retrasoMinutos: number | null;
  cancelado: boolean;
  flota: Map<string, RenfeTren>;
  onClose: () => void;
}

export function TrainMapModal({
  codComercial,
  sentido,
  horaSalida,
  horaLlegada,
  retrasoMinutos,
  cancelado,
  flota,
  onClose,
}: TrainMapModalProps) {
  const train = flota.get(codComercial);
  const icon = useMemo(() => createTrainIcon(sentido), [sentido]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // El tren pudo desaparecer de la flota (p.ej. llegó a destino) mientras la
  // modal estaba abierta; en ese caso ya no hay una posición que mostrar.
  if (!train) return null;

  const position: [number, number] = [train.latitud, train.longitud];
  const targetZoom = computeZoomForScale(train.latitud);
  const status = delayStatus(retrasoMinutos, cancelado);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Posición del tren ${codComercial}`}
      className="modal-backdrop"
      onClick={onClose}
    >
      <div className="modal-sheet glass" onClick={(event) => event.stopPropagation()}>
        <div className="modal-grabber" aria-hidden="true" />
        <div className="modal-header">
          <div>
            <h2 className="modal-title">Tren {codComercial}</h2>
            <p className="modal-subtitle">
              <span className="sentido-badge">{sentido}</span>
              {horaSalida && <span className="modal-subtitle__item">Salida {horaSalida}</span>}
              {horaLlegada && <span className="modal-subtitle__item">Llegada {horaLlegada}</span>}
              {!cancelado && (
                <span className={`status-pill status-pill--${status} modal-subtitle__item`}>
                  {formatDelay(retrasoMinutos)}
                </span>
              )}
            </p>
          </div>
          <button type="button" className="icon-btn icon-btn--glass" onClick={onClose} aria-label="Cerrar">
            ✕
          </button>
        </div>
        <div className="map-wrap">
          <MapContainer center={SPAIN_CENTER} zoom={SPAIN_ZOOM} zoomSnap={0.25} className="leaflet-fill">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Marker position={position} icon={icon} />
            <FlyToTrain position={position} zoom={targetZoom} />
          </MapContainer>
        </div>
      </div>
    </div>
  );
}
