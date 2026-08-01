export interface TodayTrain {
  cod_comercial: string;
  sentido: string;
  tipo_dia: string;
  hora_programada: string;
  hora_llegada_corregida: string | null;
  ult_retraso: number;
  capturado_en_zamora: boolean;
  entregado: boolean;
  updated_at: string;
}

export interface DayTrain {
  event_id: string;
  cod_comercial: string;
  sentido: string;
  tipo_dia: string;
  dia_semana: string;
  hora_programada: string;
  hora_llegada_corregida: string | null;
  minutos_retraso: number | null;
  cancelado: boolean;
}

export interface TrainRow {
  codComercial: string;
  sentido: string;
  horaProgramada: string;
  horaLlegada: string | null;
  retrasoMinutos: number | null;
  cancelado: boolean;
}
