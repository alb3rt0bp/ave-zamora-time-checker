import { describe, expect, it } from "vitest";
import { yesterdayMadrid } from "./dateLimits";

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
