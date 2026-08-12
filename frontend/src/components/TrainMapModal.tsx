import { useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, TileLayer } from "react-leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import type { RenfeTren } from "../types";

// Fix conocido de leaflet + bundlers: las rutas por defecto de los iconos se
// resuelven contra el HTML servido, no contra los assets empaquetados.
const trainIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const SPAIN_CENTER: [number, number] = [40.4168, -3.7038];
const SPAIN_ZOOM = 6;

interface TrainMapModalProps {
  codComercial: string;
  flota: Map<string, RenfeTren>;
  onClose: () => void;
}

export function TrainMapModal({ codComercial, flota, onClose }: TrainMapModalProps) {
  const train = flota.get(codComercial);

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
          <h2 className="modal-title">Tren {codComercial}</h2>
          <button type="button" className="icon-btn icon-btn--glass" onClick={onClose} aria-label="Cerrar">
            ✕
          </button>
        </div>
        <div className="map-wrap">
          <MapContainer center={SPAIN_CENTER} zoom={SPAIN_ZOOM} className="leaflet-fill">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Marker position={position} icon={trainIcon} />
          </MapContainer>
        </div>
      </div>
    </div>
  );
}
