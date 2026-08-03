import { useEffect, useState } from "react";
import { fetchToday } from "../api";
import type { TrainRow } from "../types";
import { normalizeTodayTrain } from "../utils/normalizeTrain";
import { TrainTable } from "./TrainTable";

export function TodayView() {
  const [rows, setRows] = useState<TrainRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // La primera carga (refreshToken=0) sustituye la tabla por el mensaje
    // de "Cargando"; un refresco posterior deja la tabla anterior visible
    // (isRefreshing) en vez de vaciarla, para no parpadear cada vez que se
    // pulsa "Refrescar".
    const isFirstLoad = refreshToken === 0;
    if (isFirstLoad) setRows(null);
    setIsRefreshing(!isFirstLoad);
    setError(null);

    fetchToday()
      .then((trains) => {
        if (!cancelled) setRows(trains.map(normalizeTodayTrain));
      })
      .catch(() => {
        if (!cancelled) setError("No se han podido cargar los trenes de hoy.");
      })
      .finally(() => {
        if (!cancelled) setIsRefreshing(false);
      });

    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  if (rows === null) {
    if (error) return <p role="alert">{error}</p>;
    return <p>Cargando trenes de hoy...</p>;
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setRefreshToken((token) => token + 1)}
        disabled={isRefreshing}
        aria-label={isRefreshing ? "Actualizando..." : "Refrescar"}
        title={isRefreshing ? "Actualizando..." : "Refrescar"}
      >
        ↻
      </button>
      {/* Un refresco fallido no debe hacer desaparecer los datos ya
          cargados: el error se muestra junto a la tabla, no en su lugar. */}
      {error && <p role="alert">{error}</p>}
      <TrainTable rows={rows} />
    </div>
  );
}
