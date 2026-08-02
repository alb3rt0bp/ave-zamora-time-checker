import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "./mocks/server";
import App from "./App";

const API_BASE_URL = "http://localhost:3000";

describe("App", () => {
  it("shows today's trains on load", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/today`, () =>
        HttpResponse.json([
          {
            cod_comercial: "04154",
            sentido: "Madrid",
            tipo_dia: "laborable",
            hora_programada: "07:41",
            hora_llegada_corregida: "07:47",
            ult_retraso: 6,
            capturado_en_zamora: true,
            entregado: true,
            updated_at: "2026-01-05T07:47:23+01:00",
          },
        ]),
      ),
    );

    render(<App />);

    expect(await screen.findByText("04154")).toBeInTheDocument();
  });

  it("swaps to a past day's trains once a date is picked", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/today`, () => HttpResponse.json([])),
      http.get(`${API_BASE_URL}/trains/:date`, () =>
        HttpResponse.json([
          {
            event_id: "04200-2026-01-04T08:00",
            cod_comercial: "04200",
            sentido: "Galicia",
            tipo_dia: "domingo",
            dia_semana: "Sunday",
            hora_programada: "08:00",
            hora_llegada_corregida: "08:05",
            minutos_retraso: 5,
            cancelado: false,
          },
        ]),
      ),
    );
    const user = userEvent.setup();

    render(<App />);
    await screen.findByText(/no hay trenes/i);

    await user.type(screen.getByLabelText(/fecha/i), "2026-01-04");

    expect(await screen.findByText("04200")).toBeInTheDocument();
  });

  it("returns to today's trains when the 'Hoy' button is clicked", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/today`, () =>
        HttpResponse.json([
          {
            cod_comercial: "04154",
            sentido: "Madrid",
            tipo_dia: "laborable",
            hora_programada: "07:41",
            hora_llegada_corregida: "07:47",
            ult_retraso: 6,
            capturado_en_zamora: true,
            entregado: true,
            updated_at: "2026-01-05T07:47:23+01:00",
          },
        ]),
      ),
      http.get(`${API_BASE_URL}/trains/:date`, () =>
        HttpResponse.json([
          {
            event_id: "04200-2026-01-04T08:00",
            cod_comercial: "04200",
            sentido: "Galicia",
            tipo_dia: "domingo",
            dia_semana: "Sunday",
            hora_programada: "08:00",
            hora_llegada_corregida: "08:05",
            minutos_retraso: 5,
            cancelado: false,
          },
        ]),
      ),
    );
    const user = userEvent.setup();

    render(<App />);
    await screen.findByText("04154");

    await user.type(screen.getByLabelText(/fecha/i), "2026-01-04");
    await screen.findByText("04200");

    await user.click(screen.getByRole("button", { name: "Hoy" }));

    expect(await screen.findByText("04154")).toBeInTheDocument();
    expect(screen.getByLabelText(/fecha/i)).toHaveValue("");
  });
});
