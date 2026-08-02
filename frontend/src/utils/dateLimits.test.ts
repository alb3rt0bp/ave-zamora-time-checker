import { describe, expect, it } from "vitest";
import { addDaysIso, yesterdayMadrid } from "./dateLimits";

describe("addDaysIso", () => {
  it("adds a positive number of days", () => {
    expect(addDaysIso("2026-01-05", 1)).toBe("2026-01-06");
  });

  it("subtracts days with a negative delta", () => {
    expect(addDaysIso("2026-01-05", -1)).toBe("2026-01-04");
  });

  it("crosses a month boundary forward", () => {
    expect(addDaysIso("2026-01-31", 1)).toBe("2026-02-01");
  });

  it("crosses a month boundary backward", () => {
    expect(addDaysIso("2026-02-01", -1)).toBe("2026-01-31");
  });

  it("crosses a year boundary", () => {
    expect(addDaysIso("2025-12-31", 1)).toBe("2026-01-01");
  });

  it("returns the same date for a zero delta", () => {
    expect(addDaysIso("2026-01-05", 0)).toBe("2026-01-05");
  });
});

describe("yesterdayMadrid", () => {
  it("returns the day before the given date, as YYYY-MM-DD", () => {
    const now = new Date("2026-01-05T10:00:00+01:00");

    expect(yesterdayMadrid(now)).toBe("2026-01-04");
  });

  it("crosses a month boundary correctly", () => {
    const now = new Date("2026-02-01T10:00:00+01:00");

    expect(yesterdayMadrid(now)).toBe("2026-01-31");
  });

  it("defaults to the current date when no argument is given", () => {
    const result = yesterdayMadrid();

    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
