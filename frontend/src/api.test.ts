import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "./mocks/server";
import { fetchByDate, fetchToday, NotFoundError } from "./api";

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
