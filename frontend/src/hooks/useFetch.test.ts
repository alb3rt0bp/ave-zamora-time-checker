import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NotFoundError } from "../api";
import { useFetch } from "./useFetch";

describe("useFetch", () => {
  it("starts in loading state", () => {
    const { result } = renderHook(() => useFetch(() => new Promise<number>(() => {}), []));

    expect(result.current).toEqual({ status: "loading" });
  });

  it("resolves to ok with the fetched data", async () => {
    const { result } = renderHook(() => useFetch(() => Promise.resolve(42), []));

    await waitFor(() => expect(result.current).toEqual({ status: "ok", data: 42 }));
  });

  it("maps a NotFoundError to the not-found status", async () => {
    const { result } = renderHook(() => useFetch(() => Promise.reject(new NotFoundError("nope")), []));

    await waitFor(() => expect(result.current).toEqual({ status: "not-found" }));
  });

  it("maps any other rejection to the error status", async () => {
    const { result } = renderHook(() => useFetch(() => Promise.reject(new Error("boom")), []));

    await waitFor(() => expect(result.current).toEqual({ status: "error" }));
  });

  it("re-fetches when deps change", async () => {
    let value = 1;
    const { result, rerender } = renderHook(
      ({ dep }: { dep: number }) => useFetch(() => Promise.resolve(value), [dep]),
      { initialProps: { dep: 1 } },
    );

    await waitFor(() => expect(result.current).toEqual({ status: "ok", data: 1 }));

    value = 2;
    rerender({ dep: 2 });

    await waitFor(() => expect(result.current).toEqual({ status: "ok", data: 2 }));
  });
});
