import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { GlobalStatsPage } from "./GlobalStatsPage";

const API_BASE_URL = "http://localhost:3000";

const GLOBAL_METRICS = {
  total_viajes: 100,
  viajes_bucket_puntual: 60,
  viajes_bucket_leve: 15,
  viajes_bucket_significativo: 15,
  viajes_bucket_grave: 10,
  pct_bucket_puntual: 60,
  pct_bucket_leve: 15,
  pct_bucket_significativo: 15,
  pct_bucket_grave: 10,
  viajes_retraso_significativo: 25,
  pct_retraso_significativo: 25,
  suma_retraso_significativo_minutos: 620,
  first_aggregated_date: "2026-07-31",
  significant_delay_threshold_minutes: 15,
  dia_semana_mas_probable: { dia_semana: 4, total_viajes: 20, viajes_retraso_significativo: 8, suma_retraso_significativo_minutos: 200, pct_retraso_significativo: 40 },
  franja_horaria_mas_probable: { franja: "tarde", total_viajes: 40, viajes_retraso_significativo: 12, suma_retraso_significativo_minutos: 300, pct_retraso_significativo: 30 },
  tren_mas_probable: { cod_comercial: "04154", sentido: "Madrid", total_viajes: 10, viajes_bucket_puntual: 2, viajes_bucket_leve: 1, viajes_bucket_significativo: 4, viajes_bucket_grave: 3, pct_bucket_puntual: 20, pct_bucket_leve: 10, pct_bucket_significativo: 40, pct_bucket_grave: 30, viajes_retraso_significativo: 7, pct_retraso_significativo: 70, suma_retraso_significativo_minutos: 400, rank_retraso: 1, total_trenes_comparados: 22 },
};

describe("GlobalStatsPage", () => {
  it("renders the chart and the three risk extremes", async () => {
    server.use(http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)));

    render(<GlobalStatsPage />);

    expect(await screen.findByText(/desde 31 de julio de 2026/)).toBeInTheDocument();
    expect(screen.getByText(/620 min/)).toBeInTheDocument();
    expect(screen.getByText("Viernes")).toBeInTheDocument(); // dia_semana=4
    expect(screen.getByText("Tarde (14-20h)")).toBeInTheDocument();
    expect(screen.getByText("04154")).toBeInTheDocument();
  });

  it("shows an empty state when there are no metrics yet (404)", async () => {
    server.use(
      http.get(`${API_BASE_URL}/metrics/global`, () =>
        HttpResponse.json({ error: "no hay métricas todavía" }, { status: 404 }),
      ),
    );

    render(<GlobalStatsPage />);

    expect(await screen.findByText(/todavía no hay datos suficientes/i)).toBeInTheDocument();
  });

  it("shows an error state on a server failure", async () => {
    server.use(http.get(`${API_BASE_URL}/metrics/global`, () => new HttpResponse(null, { status: 500 })));

    render(<GlobalStatsPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
