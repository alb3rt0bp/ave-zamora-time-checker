import type { DayTrain, TodayTrain, TrainRow } from "../types";

export function normalizeTodayTrain(train: TodayTrain): TrainRow {
  return {
    codComercial: train.cod_comercial,
    sentido: train.sentido,
    horaProgramada: train.hora_programada,
    horaLlegada: train.hora_llegada_corregida,
    // ?? null: cubre tanto null explícito (aún no capturado) como el campo
    // ausente en respuestas de una API todavía no desplegada con este campo.
    horaPasoZamora: train.hora_paso_zamora ?? null,
    retrasoMinutos: train.ult_retraso,
    cancelado: false,
  };
}

export function normalizeDayTrain(train: DayTrain): TrainRow {
  return {
    codComercial: train.cod_comercial,
    sentido: train.sentido,
    horaProgramada: train.hora_programada,
    horaLlegada: train.hora_llegada_corregida,
    // ?? null: cubre tanto null explícito (tren cancelado) como el campo
    // ausente en ficheros JSONL volcados antes de que este campo existiera.
    horaPasoZamora: train.hora_paso_zamora ?? null,
    retrasoMinutos: train.minutos_retraso,
    cancelado: train.cancelado,
  };
}
