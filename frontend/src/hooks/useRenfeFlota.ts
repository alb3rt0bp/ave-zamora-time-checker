import { useEffect, useState } from "react";
import { fetchRenfeFlota } from "../api";
import type { RenfeTren } from "../types";

const POLL_INTERVAL_MS = 15_000;

// Sondea flotaLD.json (vía el proxy /renfe/flota) desde la carga inicial y
// cada 15s en segundo plano, indexando los trenes por codComercial para que
// TrainTable pueda saber, para cada fila, si hay una posición en vivo con la
// que habilitar el enlace al mapa.
export function useRenfeFlota(): Map<string, RenfeTren> {
  const [flota, setFlota] = useState<Map<string, RenfeTren>>(new Map());

  useEffect(() => {
    let cancelled = false;

    function poll() {
      fetchRenfeFlota()
        .then((trenes) => {
          if (cancelled) return;
          setFlota(new Map(trenes.map((tren) => [tren.codComercial, tren])));
        })
        .catch(() => {
          // Un fallo puntual (red, CORS, 502 del proxy) no debe vaciar los
          // datos ya cargados; el siguiente ciclo de 15s reintenta solo.
        });
    }

    poll();
    const intervalId = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  return flota;
}
