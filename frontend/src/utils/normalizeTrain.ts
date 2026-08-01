import type { DayTrain, TodayTrain, TrainRow } from "../types";

export function normalizeTodayTrain(train: TodayTrain): TrainRow {
  return {
    codComercial: train.cod_comercial,
    sentido: train.sentido,
    horaProgramada: train.hora_programada,
    horaLlegada: train.hora_llegada_corregida,
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
    retrasoMinutos: train.minutos_retraso,
    cancelado: train.cancelado,
  };
}
