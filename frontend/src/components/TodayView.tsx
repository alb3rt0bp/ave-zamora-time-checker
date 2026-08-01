import { useEffect, useState } from "react";
import { fetchToday } from "../api";
import type { TrainRow } from "../types";
import { normalizeTodayTrain } from "../utils/normalizeTrain";
import { TrainTable } from "./TrainTable";

export function TodayView() {
  const [rows, setRows] = useState<TrainRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setError(null);

    fetchToday()
      .then((trains) => {
        if (!cancelled) setRows(trains.map(normalizeTodayTrain));
      })
      .catch(() => {
        if (!cancelled) setError("No se han podido cargar los trenes de hoy.");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (rows === null) return <p>Cargando trenes de hoy...</p>;
  return <TrainTable rows={rows} />;
}
