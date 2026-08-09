import { useEffect, useState } from "react";
import { fetchByDate, NotFoundError } from "../api";
import type { RenfeTren, TrainRow } from "../types";
import { normalizeDayTrain } from "../utils/normalizeTrain";
import { TrainTable } from "./TrainTable";

type Status = "loading" | "ok" | "not-found" | "error";

interface DayViewProps {
  date: string;
  flota?: Map<string, RenfeTren>;
}

export function DayView({ date, flota }: DayViewProps) {
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

  if (status === "loading") {
    return (
      <div className="state-card">
        <span className="spinner" aria-hidden="true" />
        <p>Cargando trenes del {date}...</p>
      </div>
    );
  }
  if (status === "not-found") return <p className="state-card">Todavía no hay datos volcados para esa fecha.</p>;
  if (status === "error")
    return (
      <p role="alert" className="state-card state-card--error">
        No se han podido cargar los trenes de esa fecha.
      </p>
    );
  return <TrainTable rows={rows} flota={flota} />;
}
