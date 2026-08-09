import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "./mocks/server";
import { fetchByDate, fetchRenfeFlota, fetchToday, NotFoundError } from "./api";

const API_BASE_URL = "http://localhost:3000";

describe("fetchToday", () => {
  it("returns the parsed list on success", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/today`, () =>
        HttpResponse.json([{ cod_comercial: "04154", sentido: "Madrid" }]),
      ),
    );

    const trains = await fetchToday();

    expect(trains).toEqual([{ cod_comercial: "04154", sentido: "Madrid" }]);
  });

  it("throws a generic error on a server failure", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/today`, () => new HttpResponse(null, { status: 500 })));

    await expect(fetchToday()).rejects.toThrow();
  });
});

describe("fetchByDate", () => {
  it("returns the parsed list on success", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/:date`, () =>
        HttpResponse.json([{ event_id: "04154-2026-01-04T07:41", cod_comercial: "04154" }]),
      ),
    );

    const trains = await fetchByDate("2026-01-04");

    expect(trains).toEqual([{ event_id: "04154-2026-01-04T07:41", cod_comercial: "04154" }]);
  });

  it("throws a NotFoundError when the day hasn't been dumped yet", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/:date`, () =>
        HttpResponse.json({ error: "no hay datos" }, { status: 404 }),
      ),
    );

    await expect(fetchByDate("2020-01-01")).rejects.toThrow(NotFoundError);
  });

  it("throws a generic error on a server failure", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/:date`, () => new HttpResponse(null, { status: 500 })));

    await expect(fetchByDate("2026-01-04")).rejects.toThrow();
  });
});

describe("fetchRenfeFlota", () => {
  it("returns the trenes list from the proxy response", async () => {
    server.use(
      http.get(`${API_BASE_URL}/renfe/flota`, () =>
        HttpResponse.json({
          fechaActualizacion: "2026-01-05T07:47:00",
          trenes: [{ codComercial: "04154", latitud: 41.5, longitud: -5.74 }],
        }),
      ),
    );

    const trenes = await fetchRenfeFlota();

    expect(trenes).toEqual([{ codComercial: "04154", latitud: 41.5, longitud: -5.74 }]);
  });

  it("throws a generic error when the proxy fails upstream", async () => {
    server.use(http.get(`${API_BASE_URL}/renfe/flota`, () => new HttpResponse(null, { status: 502 })));

    await expect(fetchRenfeFlota()).rejects.toThrow();
  });
});
