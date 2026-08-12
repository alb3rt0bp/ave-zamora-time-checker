import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { PorTiemposPage } from "./PorTiemposPage";

const API_BASE_URL = "http://localhost:3000";

function weekFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    iso_year: 2026,
    iso_week: 2,
    week_start: "2026-01-05",
    week_end: "2026-01-11",
    is_complete: true,
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
    tren_mas_probable: null,
    tren_menos_probable: null,
    dia_semana_con_mas_retrasos: null,
    dia_semana_mas_probable: null,
    dia_semana_menos_probable: null,
    ...overrides,
  };
}

function monthFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    year: 2026,
    month: 1,
    is_complete: true,
    total_viajes: 40,
    viajes_bucket_puntual: 20,
    viajes_bucket_leve: 8,
    viajes_bucket_significativo: 8,
    viajes_bucket_grave: 4,
    pct_bucket_puntual: 50,
    pct_bucket_leve: 20,
    pct_bucket_significativo: 20,
    pct_bucket_grave: 10,
    viajes_retraso_significativo: 12,
    pct_retraso_significativo: 30,
    suma_retraso_significativo_minutos: 340,
    tren_mas_probable: null,
    tren_menos_probable: null,
    dia_semana_con_mas_retrasos: null,
    dia_semana_mas_probable: null,
    dia_semana_menos_probable: null,
    ...overrides,
  };
}

describe("PorTiemposPage", () => {
  it("shows only complete weeks and defaults to the most recent", async () => {
    server.use(
      http.get(`${API_BASE_URL}/metrics/weeks`, () =>
        HttpResponse.json([
          weekFixture({ iso_week: 1, week_start: "2025-12-29", week_end: "2026-01-04", is_complete: true }),
          weekFixture({ iso_week: 2, is_complete: true, suma_retraso_significativo_minutos: 95 }),
          weekFixture({ iso_week: 3, week_start: "2026-01-12", week_end: "2026-01-18", is_complete: false }),
        ]),
      ),
      http.get(`${API_BASE_URL}/metrics/months`, () => HttpResponse.json([])),
    );

    render(<PorTiemposPage />);

    const select = await screen.findByLabelText(/selecciona una semana/i);
    const options = within(select).getAllByRole("option");
    // La semana 3 (incompleta) no debe aparecer como opción.
    expect(options).toHaveLength(2);
    expect(select).toHaveValue("2026-W2");
    expect(screen.getByText(/95 min/)).toBeInTheDocument();
  });

  it("updates the summary when a different week is selected", async () => {
    server.use(
      http.get(`${API_BASE_URL}/metrics/weeks`, () =>
        HttpResponse.json([
          weekFixture({ iso_week: 1, week_start: "2025-12-29", week_end: "2026-01-04", suma_retraso_significativo_minutos: 10 }),
          weekFixture({ iso_week: 2, suma_retraso_significativo_minutos: 95 }),
        ]),
      ),
      http.get(`${API_BASE_URL}/metrics/months`, () => HttpResponse.json([])),
    );
    const user = userEvent.setup();

    render(<PorTiemposPage />);
    const select = await screen.findByLabelText(/selecciona una semana/i);
    expect(screen.getByText(/95 min/)).toBeInTheDocument();

    await user.selectOptions(select, "2026-W1");

    expect(screen.getByText(/10 min/)).toBeInTheDocument();
  });

  it("switches to the month selector when the 'Meses' tab is clicked", async () => {
    server.use(
      http.get(`${API_BASE_URL}/metrics/weeks`, () => HttpResponse.json([weekFixture()])),
      http.get(`${API_BASE_URL}/metrics/months`, () =>
        HttpResponse.json([monthFixture({ suma_retraso_significativo_minutos: 340 })]),
      ),
    );
    const user = userEvent.setup();

    render(<PorTiemposPage />);
    await screen.findByLabelText(/selecciona una semana/i);

    await user.click(screen.getByRole("button", { name: "Meses" }));

    expect(await screen.findByLabelText(/selecciona un mes/i)).toBeInTheDocument();
    expect(screen.getByText(/340 min/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no complete weeks yet", async () => {
    server.use(
      http.get(`${API_BASE_URL}/metrics/weeks`, () =>
        HttpResponse.json([weekFixture({ is_complete: false })]),
      ),
      http.get(`${API_BASE_URL}/metrics/months`, () => HttpResponse.json([])),
    );

    render(<PorTiemposPage />);

    expect(await screen.findByText(/todavía no hay ninguna semana completa/i)).toBeInTheDocument();
  });

  it("shows an error state when a request fails", async () => {
    server.use(
      http.get(`${API_BASE_URL}/metrics/weeks`, () => new HttpResponse(null, { status: 500 })),
      http.get(`${API_BASE_URL}/metrics/months`, () => HttpResponse.json([])),
    );

    render(<PorTiemposPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
