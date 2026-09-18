import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { HorariosPage } from "./HorariosPage";

const API_BASE_URL = "http://localhost:3000";

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
    estimacion_retraso: null,
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

describe("HorariosPage", () => {
  it("groups trains under Laborables/Sábado/Domingo, showing sentido, hora de salida y llegada", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () =>
        HttpResponse.json([
          { cod_comercial: "04154", sentido: "Madrid", hora_salida: "06:56", hora_llegada_destino: "08:56", weekdays: [0, 1, 2, 3, 4] },
          { cod_comercial: "04475", sentido: "Galicia", hora_salida: "08:19", hora_llegada_destino: "09:32", weekdays: [6] },
        ]),
      ),
    );

    render(<HorariosPage />);

    expect(await screen.findByText("Laborables")).toBeInTheDocument();
    expect(screen.getByText("Domingo")).toBeInTheDocument();
    // Solo se renderizan los apartados que tienen algún tren.
    expect(screen.queryByText("Sábado")).not.toBeInTheDocument();

    const laborablesRow = screen.getByText("04154").closest("tr") as HTMLElement;
    expect(within(laborablesRow).getByText("Madrid")).toBeInTheDocument();
    expect(within(laborablesRow).getByText("06:56")).toBeInTheDocument();
    expect(within(laborablesRow).getByText("08:56")).toBeInTheDocument();

    const domingoRow = screen.getByText("04475").closest("tr") as HTMLElement;
    expect(within(domingoRow).getByText("Galicia")).toBeInTheDocument();
    expect(within(domingoRow).getByText("08:19")).toBeInTheDocument();
    expect(within(domingoRow).getByText("09:32")).toBeInTheDocument();
  });

  it("shows a weekday train only once under Laborables, even if it runs several weekdays", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () =>
        HttpResponse.json([
          { cod_comercial: "04154", sentido: "Madrid", hora_salida: "06:56", hora_llegada_destino: "08:56", weekdays: [0, 1, 2] },
        ]),
      ),
    );

    render(<HorariosPage />);

    await screen.findByText("Laborables");
    expect(screen.getAllByText("04154")).toHaveLength(1);
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
    );

    render(<HorariosPage />);

    await screen.findByText("Laborables");
    const rows = screen.getAllByRole("row").slice(1); // descarta la fila de cabecera
    expect(rows.map((row) => within(row).getByText(/^04/).textContent)).toEqual(["04154", "04157", "04160"]);
  });

  it("shows an empty state when there is no schedule", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/schedule`, () => HttpResponse.json([])));

    render(<HorariosPage />);

    expect(await screen.findByText("No hay trenes en el horario.")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/schedule`, () => new HttpResponse(null, { status: 500 })));

    render(<HorariosPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("opens the train detail modal when the train code is clicked", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () =>
        HttpResponse.json([
          { cod_comercial: "04154", sentido: "Madrid", hora_salida: "06:56", hora_llegada_destino: "08:56", weekdays: [0, 1, 2, 3, 4] },
        ]),
      ),
      http.get(`${API_BASE_URL}/metrics/trains`, () => HttpResponse.json(TRAIN_METRICS)),
      http.get(`${API_BASE_URL}/metrics/global`, () => HttpResponse.json(GLOBAL_METRICS)),
    );
    const user = userEvent.setup();
    render(<HorariosPage />);

    await user.click(await screen.findByRole("button", { name: "04154" }));

    expect(await screen.findByRole("dialog", { name: /04154/ })).toBeInTheDocument();
    expect(screen.getByText(/desde 31 de julio de 2026/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
