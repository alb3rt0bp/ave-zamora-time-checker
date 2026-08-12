import { describe, expect, it } from "vitest";
import {
  formatDelayBucketLabel,
  formatFranjaHoraria,
  formatMonthName,
  formatShortDate,
  formatSpanishDate,
  formatWeekday,
} from "./metricsFormat";

describe("formatWeekday", () => {
  it("maps 0-6 to Spanish weekday names, lunes-first", () => {
    expect(formatWeekday(0)).toBe("Lunes");
    expect(formatWeekday(6)).toBe("Domingo");
  });

  it("falls back for an out-of-range index", () => {
    expect(formatWeekday(9)).toBe("?");
  });
});

describe("formatFranjaHoraria", () => {
  it("maps known franjas to their Spanish label with hour range", () => {
    expect(formatFranjaHoraria("manana")).toBe("Mañana (06-14h)");
    expect(formatFranjaHoraria("noche")).toBe("Noche (20-06h)");
  });

  it("falls back to the raw value for an unknown franja", () => {
    expect(formatFranjaHoraria("desconocida")).toBe("desconocida");
  });
});

describe("formatDelayBucketLabel", () => {
  it("uses the default 15-minute threshold when none is given", () => {
    expect(formatDelayBucketLabel("leve")).toBe("5-15 min");
    expect(formatDelayBucketLabel("significativo")).toBe("15-60 min");
  });

  it("reflects a non-default threshold in the leve/significativo boundary", () => {
    expect(formatDelayBucketLabel("leve", 20)).toBe("5-20 min");
    expect(formatDelayBucketLabel("significativo", 20)).toBe("20-60 min");
  });

  it("puntual and grave are independent of the threshold", () => {
    expect(formatDelayBucketLabel("puntual", 20)).toBe("< 5 min");
    expect(formatDelayBucketLabel("grave", 20)).toBe("> 60 min");
  });
});

describe("formatSpanishDate", () => {
  it("formats an ISO date as a full Spanish date", () => {
    expect(formatSpanishDate("2026-07-31")).toBe("31 de julio de 2026");
  });

  it("does not lose a day to timezone offset", () => {
    expect(formatSpanishDate("2026-01-01")).toBe("1 de enero de 2026");
  });
});

describe("formatShortDate", () => {
  it("formats an ISO date as a compact day + abbreviated month", () => {
    expect(formatShortDate("2026-07-31")).toBe("31 jul");
  });
});

describe("formatMonthName", () => {
  it("maps 1-12 to Spanish month names", () => {
    expect(formatMonthName(1)).toBe("enero");
    expect(formatMonthName(12)).toBe("diciembre");
  });

  it("falls back for an out-of-range month", () => {
    expect(formatMonthName(13)).toBe("?");
  });
});
