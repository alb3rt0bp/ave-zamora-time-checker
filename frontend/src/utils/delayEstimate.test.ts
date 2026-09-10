import { describe, expect, it } from "vitest";
import { addMinutesToTime } from "./delayEstimate";

describe("addMinutesToTime", () => {
  it("adds minutes within the same hour", () => {
    expect(addMinutesToTime("18:47", 5)).toBe("18:52");
  });

  it("carries over into the next hour", () => {
    expect(addMinutesToTime("18:47", 20)).toBe("19:07");
  });

  it("returns the same time when the delay is zero", () => {
    expect(addMinutesToTime("08:56", 0)).toBe("08:56");
  });

  it("subtracts when the train runs ahead of schedule", () => {
    expect(addMinutesToTime("10:20", -3)).toBe("10:17");
  });

  it("wraps past midnight forwards", () => {
    expect(addMinutesToTime("23:55", 10)).toBe("00:05");
  });

  it("wraps past midnight backwards", () => {
    expect(addMinutesToTime("00:02", -5)).toBe("23:57");
  });

  it("keeps two digits in both fields", () => {
    expect(addMinutesToTime("09:05", 4)).toBe("09:09");
    expect(addMinutesToTime("23:59", 1)).toBe("00:00");
  });

  it("handles delays longer than an hour", () => {
    expect(addMinutesToTime("22:30", 149)).toBe("00:59");
  });
});
