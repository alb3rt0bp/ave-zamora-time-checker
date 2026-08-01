import { useEffect, useState } from "react";
import { fetchByDate, NotFoundError } from "../api";
import type { TrainRow } from "../types";
import { normalizeDayTrain } from "../utils/normalizeTrain";
import { TrainTable } from "./TrainTable";

type Status = "loading" | "ok" | "not-found" | "error";

interface DayViewProps {
  date: string;
}

export function DayView({ date }: DayViewProps) {
  const [rows, setRows] = useState<TrainRow[]>([]);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setRows([]);

    fetchByDate(date)
      .then((trains) => {
        if (cancelled) return;
        setRows(trains.map(normalizeDayTrain));
        setStatus("ok");
      })
      .catch((err) => {
        if (cancelled) return;
        setStatus(err instanceof NotFoundError ? "not-found" : "error");
      });

    return () => {
      cancelled = true;
    };
  }, [date]);

  if (status === "loading") return <p>Cargando trenes del {date}...</p>;
  if (status === "not-found") return <p>Todavía no hay datos volcados para esa fecha.</p>;
  if (status === "error") return <p role="alert">No se han podido cargar los trenes de esa fecha.</p>;
  return <TrainTable rows={rows} />;
}
