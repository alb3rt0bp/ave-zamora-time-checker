import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "../mocks/server";
import { useRenfeFlota } from "./useRenfeFlota";

const API_BASE_URL = "http://localhost:3000";

describe("useRenfeFlota", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches the fleet on mount and indexes trains by codComercial", async () => {
    server.use(
      http.get(`${API_BASE_URL}/renfe/flota`, () =>
        HttpResponse.json({
          fechaActualizacion: "2026-01-05T07:47:00",
          trenes: [{ codComercial: "04154", latitud: 41.5, longitud: -5.74 }],
        }),
      ),
    );

    const { result } = renderHook(() => useRenfeFlota());

    await waitFor(() => expect(result.current.size).toBe(1));
    expect(result.current.get("04154")).toEqual({ codComercial: "04154", latitud: 41.5, longitud: -5.74 });
  });

  it("re-fetches every 15 seconds and updates the map with fresh positions", async () => {
    let callCount = 0;
    server.use(
      http.get(`${API_BASE_URL}/renfe/flota`, () => {
        callCount += 1;
        const longitud = callCount === 1 ? -5.74 : -5.5;
        return HttpResponse.json({
          fechaActualizacion: "2026-01-05T07:47:00",
          trenes: [{ codComercial: "04154", latitud: 41.5, longitud }],
        });
      }),
    );

    const { result } = renderHook(() => useRenfeFlota());
    await waitFor(() => expect(result.current.get("04154")?.longitud).toBe(-5.74));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });

    await waitFor(() => expect(result.current.get("04154")?.longitud).toBe(-5.5));
  });

  it("keeps the previous data when a poll fails", async () => {
    server.use(
      http.get(`${API_BASE_URL}/renfe/flota`, () =>
        HttpResponse.json({
          fechaActualizacion: "2026-01-05T07:47:00",
          trenes: [{ codComercial: "04154", latitud: 41.5, longitud: -5.74 }],
        }),
      ),
    );

    const { result } = renderHook(() => useRenfeFlota());
    await waitFor(() => expect(result.current.size).toBe(1));

    server.use(http.get(`${API_BASE_URL}/renfe/flota`, () => new HttpResponse(null, { status: 502 })));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });

    expect(result.current.get("04154")).toEqual({ codComercial: "04154", latitud: 41.5, longitud: -5.74 });
  });
});
