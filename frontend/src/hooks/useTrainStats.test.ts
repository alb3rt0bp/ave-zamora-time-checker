import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../mocks/server";
import { useTrainStats } from "./useTrainStats";

const API_BASE_URL = "http://localhost:3000";

const trainMetrics = {
  cod_comercial: "04154",
  sentido: "Madrid",
  rank_retraso: 3,
  total_trenes_comparados: 54,
  estimacion_retraso: null,
  total_viajes: 42,
  viajes_bucket_puntual: 20,
  viajes_bucket_leve: 12,
  viajes_bucket_significativo: 7,
  viajes_bucket_grave: 3,
  pct_bucket_puntual: 47.6,
  pct_bucket_leve: 28.6,
  pct_bucket_significativo: 16.7,
  pct_bucket_grave: 7.1,
  viajes_retraso_significativo: 10,
  pct_retraso_significativo: 23.8,
  suma_retraso_significativo_minutos: 214,
};

describe("useTrainStats", () => {
  it("indexes the train metrics by codComercial", async () => {
    server.use(http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json([trainMetrics])));

    const { result } = renderHook(() => useTrainStats());

    await waitFor(() => expect(result.current.metrics.size).toBe(1));
    expect(result.current.metrics.get("04154")).toEqual(trainMetrics);
  });

  it("exposes the global metrics when they are available", async () => {
    server.use(
      http.get(`${API_BASE_URL}/metrics/global`, () =>
        HttpResponse.json({ first_aggregated_date: "2026-07-30", significant_delay_threshold_minutes: 15 }),
      ),
    );

    const { result } = renderHook(() => useTrainStats());

    await waitFor(() => expect(result.current.globalMetrics).not.toBeNull());
    expect(result.current.globalMetrics?.first_aggregated_date).toBe("2026-07-30");
  });

  // Los handlers por defecto responden 404 a /metrics/global (ningún día
  // agregado todavía): el detalle del tren debe seguir abriéndose, solo que
  // sin poder fechar "desde cuándo" se acumulan las estadísticas.
  it("keeps the global metrics null when they don't exist yet", async () => {
    server.use(http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json([trainMetrics])));

    const { result } = renderHook(() => useTrainStats());

    await waitFor(() => expect(result.current.metrics.size).toBe(1));
    expect(result.current.globalMetrics).toBeNull();
  });

  it("keeps empty stats when the metrics fetch fails", async () => {
    server.use(http.get(`${API_BASE_URL}/metrics/trains`, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useTrainStats());

    // Como en useTrainSchedule: no hay forma determinista de esperar "no
    // cambiará nunca", así que se comprueba el único estado posible tras el
    // fallo, que es el inicial.
    expect(result.current.metrics.size).toBe(0);
    expect(result.current.globalMetrics).toBeNull();
  });

  it("ignores a response that resolves after unmounting", async () => {
    let resolveResponse!: () => void;
    const responseReady = new Promise<void>((resolve) => {
      resolveResponse = resolve;
    });
    server.use(
      http.get(`${API_BASE_URL}/metrics/trains`, async () => {
        await responseReady;
        return HttpResponse.json([]);
      }),
    );
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const { unmount } = renderHook(() => useTrainStats());
    unmount();
    resolveResponse();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
