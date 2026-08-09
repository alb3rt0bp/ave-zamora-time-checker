export interface TodayTrain {
  cod_comercial: string;
  sentido: string;
  tipo_dia: string;
  hora_programada: string;
  hora_llegada_corregida: string | null;
  hora_paso_zamora: string | null;
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
  // Ausente (no solo null) en ficheros JSONL volcados antes de que este
  // campo existiera; el resto de campos ya estaban desde el primer volcado.
  hora_paso_zamora?: string | null;
  minutos_retraso: number | null;
  cancelado: boolean;
}

export interface TrainRow {
  codComercial: string;
  sentido: string;
  horaProgramada: string;
  horaLlegada: string | null;
  horaPasoZamora: string | null;
  retrasoMinutos: number | null;
  cancelado: boolean;
}

// Posición en vivo de un tren, tal y como la publica flotaLD.json (vía el
// proxy /renfe/flota, necesario porque el endpoint de Renfe no envía
// cabeceras CORS y el navegador no puede consultarlo directamente).
export interface RenfeTren {
  codComercial: string;
  latitud: number;
  longitud: number;
}
