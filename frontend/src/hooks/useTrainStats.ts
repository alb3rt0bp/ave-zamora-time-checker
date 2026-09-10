import { useEffect, useState } from "react";
import { fetchGlobalMetrics, fetchTrainMetrics } from "../api";
import type { GlobalMetrics, TrainMetrics } from "../types";

// Estadísticas de puntualidad ya agregadas (/metrics/trains + /metrics/global),
// pedidas una sola vez como useTrainSchedule: son datos históricos, no cambian
// durante la sesión. Alimentan el modal de detalle que TrainTable abre desde
// cualquier día, no solo desde las páginas de Estadísticas.
export function useTrainStats(): {
  metrics: Map<string, TrainMetrics>;
  globalMetrics: GlobalMetrics | null;
} {
  const [metrics, setMetrics] = useState<Map<string, TrainMetrics>>(new Map());
  const [globalMetrics, setGlobalMetrics] = useState<GlobalMetrics | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchTrainMetrics()
      .then((trains) => {
        if (cancelled) return;
        setMetrics(new Map(trains.map((train) => [train.cod_comercial, train])));
      })
      .catch(() => {
        // Sin métricas, el modal de detalle sigue abriéndose y muestra su
        // propio estado vacío; no debe romper la tabla de trenes.
      });

    // Un 404 aquí (ningún volcado agregado todavía) es un caso normal, no un
    // error: solo significa que el modal no podrá decir "desde <fecha>".
    fetchGlobalMetrics()
      .then((global) => {
        if (!cancelled) setGlobalMetrics(global);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, []);

  return { metrics, globalMetrics };
}
