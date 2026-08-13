import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { PorTrenesPage } from "./PorTrenesPage";

const API_BASE_URL = "http://localhost:3000";

const SCHEDULE = [
  { cod_comercial: "04154", sentido: "Madrid", hora_salida: "06:56", hora_llegada_destino: "08:56", weekdays: [0] },
  { cod_comercial: "04475", sentido: "Galicia", hora_salida: "20:19", hora_llegada_destino: "21:32", weekdays: [6] },
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
  it("groups trains under Laborables (L-V) or Sábado/Domingo", async () => {
    mockHappyPath();
    render(<PorTrenesPage />);

    expect(await screen.findByText("Laborables")).toBeInTheDocument();
    expect(screen.getByText("Domingo")).toBeInTheDocument();
    expect(screen.getByText("04154 · Madrid")).toBeInTheDocument();
    expect(screen.getByText("04475 · Galicia")).toBeInTheDocument();
    // Solo se renderizan los apartados que tienen algún tren.
    expect(screen.queryByText("Sábado")).not.toBeInTheDocument();
  });

  it("shows a weekday train only once under Laborables, even if it runs several weekdays", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () =>
        HttpResponse.json([
          { cod_comercial: "04154", sentido: "Madrid", hora_salida: "06:56", hora_llegada_destino: "08:56", weekdays: [0, 1, 2] },
        ]),
      ),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
      http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)),
    );

    render(<PorTrenesPage />);

    await screen.findByText("Laborables");
    expect(screen.queryByText("Martes")).not.toBeInTheDocument();
    expect(screen.getAllByText("04154 · Madrid")).toHaveLength(1);
  });

  it("orders trains within a group by scheduled departure time", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () =>
        HttpResponse.json([
          { cod_comercial: "04160", sentido: "Madrid", hora_salida: "18:30", hora_llegada_destino: "20:30", weekdays: [0] },
          { cod_comercial: "04154", sentido: "Madrid", hora_salida: "06:56", hora_llegada_destino: "08:56", weekdays: [0] },
          { cod_comercial: "04157", sentido: "Madrid", hora_salida: "12:10", hora_llegada_destino: "14:10", weekdays: [0] },
        ]),
      ),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
      http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)),
    );

    render(<PorTrenesPage />);

    await screen.findByText("Laborables");
    const chips = screen.getAllByRole("button", { name: /04/ });
    expect(chips.map((chip) => chip.textContent)).toEqual([
      "04154 · Madrid",
      "04157 · Madrid",
      "04160 · Madrid",
    ]);
  });

  it("opens the stats modal with the train's metrics when a chip is clicked", async () => {
    mockHappyPath();
    const user = userEvent.setup();
    render(<PorTrenesPage />);

    await user.click(await screen.findByText("04154 · Madrid"));

    expect(await screen.findByRole("dialog", { name: /04154/ })).toBeInTheDocument();
    expect(screen.getByText(/desde 31 de julio de 2026/)).toBeInTheDocument();
    expect(screen.getByText("Salida 06:56")).toBeInTheDocument();
    expect(screen.getByText("Llegada 08:56")).toBeInTheDocument();
  });

  it("shows an empty state for a train with no metrics yet", async () => {
    mockHappyPath();
    const user = userEvent.setup();
    render(<PorTrenesPage />);

    await user.click(await screen.findByText("04475 · Galicia"));

    expect(await screen.findByText(/todavía no hay datos/i)).toBeInTheDocument();
  });

  it("closes the stats modal when the close button is clicked", async () => {
    mockHappyPath();
    const user = userEvent.setup();
    render(<PorTrenesPage />);

    await user.click(await screen.findByText("04154 · Madrid"));
    await screen.findByRole("dialog", { name: /04154/ });

    await user.click(screen.getByRole("button", { name: "Cerrar" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an empty state when there is no schedule at all", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () => HttpResponse.json([])),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json([])),
      http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)),
    );

    render(<PorTrenesPage />);

    expect(await screen.findByText("No hay trenes en el horario.")).toBeInTheDocument();
  });

  it("propagates a real error from /metrics/global instead of swallowing it", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () => HttpResponse.json(SCHEDULE)),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
      http.get(`${API_BASE_URL}/metrics/global`, () => new HttpResponse(null, { status: 500 })),
    );

    render(<PorTrenesPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
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
