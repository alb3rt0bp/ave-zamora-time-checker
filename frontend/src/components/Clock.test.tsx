import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Clock } from "./Clock";

describe("Clock", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the current date and time converted to Europe/Madrid (CET, UTC+1 in winter)", () => {
    vi.setSystemTime(new Date("2026-01-05T10:15:30Z"));

    render(<Clock />);

    expect(screen.getByText(/11:15:30/)).toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it("accounts for the CEST offset (UTC+2 in summer)", () => {
    vi.setSystemTime(new Date("2026-07-05T10:15:30Z"));

    render(<Clock />);

    expect(screen.getByText(/12:15:30/)).toBeInTheDocument();
  });

  it("ticks forward every second on its own", () => {
    vi.setSystemTime(new Date("2026-01-05T10:15:30Z"));
    render(<Clock />);
    expect(screen.getByText(/11:15:30/)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText(/11:15:31/)).toBeInTheDocument();
  });

  it("stops ticking after unmount instead of updating state on an unmounted component", () => {
    vi.setSystemTime(new Date("2026-01-05T10:15:30Z"));
    const { unmount } = render(<Clock />);

    unmount();

    expect(() => act(() => vi.advanceTimersByTime(5000))).not.toThrow();
  });
});
