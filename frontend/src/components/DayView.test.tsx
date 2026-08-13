import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../mocks/server";
import { DayView } from "./DayView";

const API_BASE_URL = "http://localhost:3000";

describe("DayView", () => {
  it("shows a loading state before the data arrives", () => {
    render(<DayView date="2026-01-04" />);

    expect(screen.getByText(/cargando/i)).toBeInTheDocument();
  });

  it("renders the day's trains once loaded", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/:date`, () =>
        HttpResponse.json([
          {
            event_id: "04154-2026-01-04T07:41",
            cod_comercial: "04154",
            sentido: "Madrid",
            tipo_dia: "domingo",
            dia_semana: "Sunday",
            hora_programada: "07:41",
            hora_llegada_corregida: "07:47",
            minutos_retraso: 6,
            cancelado: false,
          },
        ]),
      ),
    );

    render(<DayView date="2026-01-04" />);

    expect(await screen.findByText("04154")).toBeInTheDocument();
  });

  it("shows a not-dumped-yet message on 404", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/:date`, () =>
        HttpResponse.json({ error: "no hay datos" }, { status: 404 }),
      ),
    );

    render(<DayView date="2026-01-04" />);

    expect(await screen.findByText(/todavía no hay datos/i)).toBeInTheDocument();
  });

  it("shows an error message on a server failure", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/:date`, () => new HttpResponse(null, { status: 500 })));

    render(<DayView date="2026-01-04" />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("ignores a response that resolves after the component has unmounted", async () => {
    let resolveResponse!: () => void;
    const responseReady = new Promise<void>((resolve) => {
      resolveResponse = resolve;
    });
    server.use(
      http.get(`${API_BASE_URL}/trains/:date`, async () => {
        await responseReady;
        return HttpResponse.json([]);
      }),
    );
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const { unmount } = render(<DayView date="2026-01-04" />);
    unmount();
    resolveResponse();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
