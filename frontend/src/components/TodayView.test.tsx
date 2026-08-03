import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { TodayView } from "./TodayView";

const API_BASE_URL = "http://localhost:3000";

const SAMPLE_TRAIN = {
  cod_comercial: "04154",
  sentido: "Madrid",
  tipo_dia: "laborable",
  hora_programada: "07:41",
  hora_llegada_corregida: "07:47",
  ult_retraso: 6,
  capturado_en_zamora: true,
  entregado: true,
  updated_at: "2026-01-05T07:47:23+01:00",
};

describe("TodayView", () => {
  it("shows a loading state before the data arrives", () => {
    render(<TodayView />);

    expect(screen.getByText(/cargando/i)).toBeInTheDocument();
  });

  it("renders today's trains once loaded", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/today`, () => HttpResponse.json([SAMPLE_TRAIN])));

    render(<TodayView />);

    expect(await screen.findByText("04154")).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/today`, () => new HttpResponse(null, { status: 500 })));

    render(<TodayView />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/no se han podido cargar/i);
  });

  it("shows a 'Refrescar' button once the trains have loaded", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/today`, () => HttpResponse.json([SAMPLE_TRAIN])));

    render(<TodayView />);
    await screen.findByText("04154");

    expect(screen.getByRole("button", { name: "Refrescar" })).toBeInTheDocument();
  });

  it("refetches and updates the table when 'Refrescar' is clicked", async () => {
    let callCount = 0;
    server.use(
      http.get(`${API_BASE_URL}/trains/today`, () => {
        callCount += 1;
        const cod = callCount === 1 ? "04154" : "04200";
        return HttpResponse.json([{ ...SAMPLE_TRAIN, cod_comercial: cod }]);
      }),
    );
    const user = userEvent.setup();

    render(<TodayView />);
    await screen.findByText("04154");

    await user.click(screen.getByRole("button", { name: "Refrescar" }));

    expect(await screen.findByText("04200")).toBeInTheDocument();
  });

  it("disables the button and labels it 'Actualizando...' while a refresh is in flight", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/today`, async () => {
        await delay(50);
        return HttpResponse.json([SAMPLE_TRAIN]);
      }),
    );
    const user = userEvent.setup();

    render(<TodayView />);
    await screen.findByText("04154");

    await user.click(screen.getByRole("button", { name: "Refrescar" }));

    expect(screen.getByRole("button", { name: "Actualizando..." })).toBeDisabled();
    expect(await screen.findByRole("button", { name: "Refrescar" })).not.toBeDisabled();
  });

  it("keeps the previously loaded table visible (with an inline error) if a refresh fails", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/today`, () => HttpResponse.json([SAMPLE_TRAIN])));
    const user = userEvent.setup();

    render(<TodayView />);
    await screen.findByText("04154");

    server.use(http.get(`${API_BASE_URL}/trains/today`, () => new HttpResponse(null, { status: 500 })));
    await user.click(screen.getByRole("button", { name: "Refrescar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/no se han podido cargar/i);
    expect(screen.getByText("04154")).toBeInTheDocument();
  });
});
