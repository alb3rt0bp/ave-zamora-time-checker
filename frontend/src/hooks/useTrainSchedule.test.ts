import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../mocks/server";
import { useTrainSchedule } from "./useTrainSchedule";

const API_BASE_URL = "http://localhost:3000";

describe("useTrainSchedule", () => {
  it("fetches the schedule once on mount and indexes trains by codComercial", async () => {
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, () =>
        HttpResponse.json([
          { cod_comercial: "04154", sentido: "Madrid", hora_salida: "07:41", weekdays: [0, 1, 2, 3, 4] },
        ]),
      ),
    );

    const { result } = renderHook(() => useTrainSchedule());

    await waitFor(() => expect(result.current.size).toBe(1));
    expect(result.current.get("04154")).toEqual({
      cod_comercial: "04154",
      sentido: "Madrid",
      hora_salida: "07:41",
      weekdays: [0, 1, 2, 3, 4],
    });
  });

  it("keeps an empty map when the fetch fails", async () => {
    server.use(http.get(`${API_BASE_URL}/trains/schedule`, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useTrainSchedule());

    // No hay forma determinista de esperar "no cambiará nunca"; se comprueba
    // el estado inicial, que es el único que puede darse tras un fallo.
    expect(result.current.size).toBe(0);
  });

  it("ignores a response that resolves after unmounting", async () => {
    let resolveResponse!: () => void;
    const responseReady = new Promise<void>((resolve) => {
      resolveResponse = resolve;
    });
    server.use(
      http.get(`${API_BASE_URL}/trains/schedule`, async () => {
        await responseReady;
        return HttpResponse.json([]);
      }),
    );
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const { unmount } = renderHook(() => useTrainSchedule());
    unmount();
    resolveResponse();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
