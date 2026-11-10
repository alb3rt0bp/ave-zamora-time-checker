import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useMediaQuery } from "./useMediaQuery";

function fakeMediaQueryList(initial: boolean) {
  const listeners = new Set<() => void>();
  const mediaQueryList = {
    matches: initial,
    addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
  };
  vi.spyOn(window, "matchMedia").mockReturnValue(mediaQueryList as unknown as MediaQueryList);
  return {
    listeners,
    change(next: boolean) {
      mediaQueryList.matches = next;
      listeners.forEach((listener) => listener());
    },
  };
}

describe("useMediaQuery", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns whether the query currently matches", () => {
    fakeMediaQueryList(true);

    const { result } = renderHook(() => useMediaQuery("(max-width: 639px)"));

    expect(result.current).toBe(true);
  });

  it("updates when the query starts or stops matching", () => {
    const media = fakeMediaQueryList(false);
    const { result } = renderHook(() => useMediaQuery("(max-width: 639px)"));

    act(() => media.change(true));

    expect(result.current).toBe(true);
  });

  it("stops listening once unmounted", () => {
    const media = fakeMediaQueryList(false);
    const { unmount } = renderHook(() => useMediaQuery("(max-width: 639px)"));

    unmount();

    expect(media.listeners.size).toBe(0);
  });
});
