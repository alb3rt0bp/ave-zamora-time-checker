import { useEffect, useState } from "react";
import { NotFoundError } from "../api";

export type FetchState<T> =
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "not-found" }
  | { status: "error" };

// Generaliza el ciclo loading/ok/not-found/error ya usado en DayView.tsx
// (ver Status ahí), para las páginas de Estadísticas que lo repiten varias
// veces (modal de tren, semanas/meses, global) sobre distintos endpoints.
// fetcher se llama de nuevo solo cuando cambia `deps` (no en cada render;
// por eso no forma parte del array de dependencias del propio hook).
export function useFetch<T>(fetcher: () => Promise<T>, deps: readonly unknown[]): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: "ok", data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({ status: err instanceof NotFoundError ? "not-found" : "error" });
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
