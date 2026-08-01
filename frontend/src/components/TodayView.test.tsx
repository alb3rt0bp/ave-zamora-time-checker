import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { TodayView } from "./TodayView";

const API_BASE_URL = "http://localhost:3000";

describe("TodayView", () => {
  it("shows a loading state before the data arrives", () => {
    render(<TodayView />);

    expect(screen.getByText(/cargando/i)).toBeInTheDocument();
  });

  it("renders today's trains once loaded", async () => {
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

    render(<TodayView />);

    expect(await screen.findByText("04154")).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/today`, () => new HttpResponse(null, { status: 500 })));

    render(<TodayView />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/no se han podido cargar/i);
  });
});
