import { describe, expect, it } from "vitest";
import { normalizeDayTrain, normalizeTodayTrain } from "./normalizeTrain";
import type { DayTrain, TodayTrain } from "../types";

describe("normalizeTodayTrain", () => {
  it("maps today's DynamoDB-shaped fields to a TrainRow", () => {
    const train: TodayTrain = {
      cod_comercial: "04154",
      sentido: "Madrid",
      tipo_dia: "laborable",
      hora_programada: "07:41",
      hora_llegada_corregida: "07:47",
      ult_retraso: 6,
      capturado_en_zamora: true,
      entregado: true,
      updated_at: "2026-01-05T07:47:23+01:00",
    };

    expect(normalizeTodayTrain(train)).toEqual({
      codComercial: "04154",
      sentido: "Madrid",
      horaProgramada: "07:41",
      horaLlegada: "07:47",
      retrasoMinutos: 6,
      cancelado: false,
    });
  });
});

describe("normalizeDayTrain", () => {
  it("maps a past-day JSONL record to a TrainRow", () => {
    const train: DayTrain = {
      event_id: "04154-2026-01-04T07:41",
      cod_comercial: "04154",
      sentido: "Madrid",
      tipo_dia: "domingo",
      dia_semana: "Sunday",
      hora_programada: "07:41",
      hora_llegada_corregida: "07:47",
      minutos_retraso: 6,
      cancelado: false,
    };

    expect(normalizeDayTrain(train)).toEqual({
      codComercial: "04154",
      sentido: "Madrid",
      horaProgramada: "07:41",
      horaLlegada: "07:47",
      retrasoMinutos: 6,
      cancelado: false,
    });
  });

  it("marks a cancelled train with null delay/arrival data", () => {
    const train: DayTrain = {
      event_id: "04200-2026-01-04T08:00",
      cod_comercial: "04200",
      sentido: "Galicia",
      tipo_dia: "domingo",
      dia_semana: "Sunday",
      hora_programada: "08:00",
      hora_llegada_corregida: null,
      minutos_retraso: null,
      cancelado: true,
    };

    expect(normalizeDayTrain(train)).toEqual({
      codComercial: "04200",
      sentido: "Galicia",
      horaProgramada: "08:00",
      horaLlegada: null,
      retrasoMinutos: null,
      cancelado: true,
    });
  });
});
