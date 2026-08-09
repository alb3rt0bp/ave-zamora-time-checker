import { describe, expect, it } from "vitest";
import { delayStatus, formatDelay, isCancelled, isTrainLate } from "./trainFormat";

describe("formatDelay", () => {
  it("formats zero delay as on-time", () => {
    expect(formatDelay(0)).toBe("Puntual");
  });

  it("formats a positive delay with a plus sign and unit", () => {
    expect(formatDelay(6)).toBe("+6 min");
  });

  it("formats a negative delay with a single minus sign and unit", () => {
    expect(formatDelay(-5)).toBe("-5 min");
  });

  it("formats null as no data", () => {
    expect(formatDelay(null)).toBe("Sin datos");
  });
});

describe("isTrainLate", () => {
  it("is false when delay is under the default threshold", () => {
    expect(isTrainLate(5)).toBe(false);
  });

  it("is true when delay exceeds the default threshold", () => {
    expect(isTrainLate(15)).toBe(true);
  });

  it("respects a custom threshold", () => {
    expect(isTrainLate(12, 20)).toBe(false);
    expect(isTrainLate(25, 20)).toBe(true);
  });

  it("is false when there is no delay data", () => {
    expect(isTrainLate(null)).toBe(false);
  });
});

describe("isCancelled", () => {
  it("is true when cancelado is true", () => {
    expect(isCancelled({ cancelado: true })).toBe(true);
  });

  it("is false when cancelado is false", () => {
    expect(isCancelled({ cancelado: false })).toBe(false);
  });

  it("is false when cancelado is absent", () => {
    expect(isCancelled({})).toBe(false);
  });
});

describe("delayStatus", () => {
  it("is 'danger' for a cancelled train regardless of its stale delay value", () => {
    expect(delayStatus(90, true)).toBe("danger");
    expect(delayStatus(null, true)).toBe("danger");
  });

  it("is 'neutral' when there is no delay data", () => {
    expect(delayStatus(null, false)).toBe("neutral");
  });

  it("is 'ok' for on-time and small delays (10 min or less)", () => {
    expect(delayStatus(0, false)).toBe("ok");
    expect(delayStatus(10, false)).toBe("ok");
  });

  it("is 'warn' for delays over 10 up to 15 minutes", () => {
    expect(delayStatus(11, false)).toBe("warn");
    expect(delayStatus(15, false)).toBe("warn");
  });

  it("is 'danger' for delays over 15 minutes", () => {
    expect(delayStatus(16, false)).toBe("danger");
  });
});
