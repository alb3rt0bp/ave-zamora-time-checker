import { useEffect, useState } from "react";
import { fetchTrainSchedule } from "../api";
import type { TrainSchedule } from "../types";

// A diferencia de useRenfeFlota, el horario programado es config estática
// (config/train_schedules.json vía /trains/schedule): se pide una sola vez,
// sin sondeo periódico, e indexado por codComercial para que TrainTable
// pueda anexar la hora de salida programada a cada fila.
export function useTrainSchedule(): Map<string, TrainSchedule> {
  const [schedule, setSchedule] = useState<Map<string, TrainSchedule>>(new Map());

  useEffect(() => {
    let cancelled = false;

    fetchTrainSchedule()
      .then((trains) => {
        if (cancelled) return;
        setSchedule(new Map(trains.map((train) => [train.cod_comercial, train])));
      })
      .catch(() => {
        // Sin horario disponible, TrainTable simplemente mostrará "-" en la
        // columna de hora de salida; no debe romper el resto de la vista.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return schedule;
}
