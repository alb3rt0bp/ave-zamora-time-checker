import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { PorTrenesPage } from "./PorTrenesPage";

const API_BASE_URL = "http://localhost:3000";

const SCHEDULE = [
  { cod_comercial: "04154", sentido: "Madrid", weekdays: [0] },
  { cod_comercial: "04475", sentido: "Galicia", weekdays: [6] },
];

const TRAIN_METRICS = [
  {
    cod_comercial: "04154",
    sentido: "Madrid",
    total_viajes: 10,
    viajes_bucket_puntual: 6,
    viajes_bucket_leve: 1,
    viajes_bucket_significativo: 2,
    viajes_bucket_grave: 1,
    pct_bucket_puntual: 60,
    pct_bucket_leve: 10,
    pct_bucket_significativo: 20,
    pct_bucket_grave: 10,
    viajes_retraso_significativo: 3,
    pct_retraso_significativo: 30,
    suma_retraso_significativo_minutos: 95,
    rank_retraso: 1,
    total_trenes_comparados: 2,
  },
];

const GLOBAL_METRICS = {
  total_viajes: 10,
  viajes_bucket_puntual: 6,
  viajes_bucket_leve: 1,
  viajes_bucket_significativo: 2,
  viajes_bucket_grave: 1,
  pct_bucket_puntual: 60,
  pct_bucket_leve: 10,
  pct_bucket_significativo: 20,
  pct_bucket_grave: 10,
  viajes_retraso_significativo: 3,
  pct_retraso_significativo: 30,
  suma_retraso_significativo_minutos: 95,
  first_aggregated_date: "2026-07-31",
  significant_delay_threshold_minutes: 15,
  dia_semana_mas_probable: null,
  franja_horaria_mas_probable: null,
  tren_mas_probable: null,
};

function mockHappyPath() {
  server.use(
    http.get(`${API_BASE_URL}/trains/schedule`, () => HttpResponse.json(SCHEDULE)),
    http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
    http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)),
  );
}

describe("PorTrenesPage", () => {
  it("groups trains under the weekdays they operate on", async () => {
    mockHappyPath();
    render(<PorTrenesPage />);

    expect(await screen.findByText("Lunes")).toBeInTheDocument();
    expect(screen.getByText("Domingo")).toBeInTheDocument();
    expect(screen.getByText("04154 · Madrid")).toBeInTheDocument();
    expect(screen.getByText("04475 · Galicia")).toBeInTheDocument();
    // Solo se renderizan los días de la semana que tienen algún tren.
    expect(screen.queryByText("Sábado")).not.toBeInTheDocument();
  });

  it("repeats a train under every weekday it operates on", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () =>
        HttpResponse.json([{ cod_comercial: "04154", sentido: "Madrid", weekdays: [0, 1, 2] }]),
      ),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
      http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)),
    );

    render(<PorTrenesPage />);

    await screen.findByText("Lunes");
    expect(screen.getByText("Martes")).toBeInTheDocument();
    expect(screen.getByText("Miércoles")).toBeInTheDocument();
    expect(screen.getAllByText("04154 · Madrid")).toHaveLength(3);
  });

  it("opens the stats modal with the train's metrics when a chip is clicked", async () => {
    mockHappyPath();
    const user = userEvent.setup();
    render(<PorTrenesPage />);

    await user.click(await screen.findByText("04154 · Madrid"));

    expect(await screen.findByRole("dialog", { name: /04154/ })).toBeInTheDocument();
    expect(screen.getByText(/desde 31 de julio de 2026/)).toBeInTheDocument();
  });

  it("shows an empty state for a train with no metrics yet", async () => {
    mockHappyPath();
    const user = userEvent.setup();
    render(<PorTrenesPage />);

    await user.click(await screen.findByText("04475 · Galicia"));

    expect(await screen.findByText(/todavía no hay datos/i)).toBeInTheDocument();
  });

  it("still renders the train list when /metrics/global has no data yet", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () => HttpResponse.json(SCHEDULE)),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
      http.get(`${API_BASE_URL}/metrics/global`, () =>
        HttpResponse.json({ error: "no hay métricas todavía" }, { status: 404 }),
      ),
    );

    render(<PorTrenesPage />);

    expect(await screen.findByText("04154 · Madrid")).toBeInTheDocument();
  });

  it("shows an error state when a request fails", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () => new HttpResponse(null, { status: 500 })),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
      http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)),
    );

    render(<PorTrenesPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
