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

// ── Estadísticas de puntualidad (/metrics/*, /trains/schedule) ─────────────

// Los 4 tramos de retraso (para el gráfico de tipo queso) + el agregado
// "retraso significativo" (tramos significativo+grave), compartidos por
// items de tren/semana/mes/global.
export interface DelayBuckets {
  total_viajes: number;
  viajes_bucket_puntual: number;
  viajes_bucket_leve: number;
  viajes_bucket_significativo: number;
  viajes_bucket_grave: number;
  pct_bucket_puntual: number;
  pct_bucket_leve: number;
  pct_bucket_significativo: number;
  pct_bucket_grave: number;
  viajes_retraso_significativo: number;
  pct_retraso_significativo: number;
  suma_retraso_significativo_minutos: number;
}

export interface TrainMetrics extends DelayBuckets {
  cod_comercial: string;
  sentido: string;
  rank_retraso: number;
  total_trenes_comparados: number;
}

// Resumen reducido de un tren dentro de una semana/mes concretos (no lleva
// los 4 tramos completos, solo lo necesario para el ranking de ese periodo).
export interface TrainRiskSummary {
  cod_comercial: string;
  total_viajes: number;
  viajes_retraso_significativo: number;
  pct_retraso_significativo: number;
}

export interface WeekdayRiskSummary {
  dia_semana: number; // 0=lunes .. 6=domingo
  total_viajes: number;
  viajes_retraso_significativo: number;
  suma_retraso_significativo_minutos: number;
  pct_retraso_significativo: number;
}

export interface FranjaHorariaRiskSummary {
  franja: "manana" | "tarde" | "noche";
  total_viajes: number;
  viajes_retraso_significativo: number;
  suma_retraso_significativo_minutos: number;
  pct_retraso_significativo: number;
}

interface PeriodExtremes {
  tren_mas_probable: TrainRiskSummary | null;
  tren_menos_probable: TrainRiskSummary | null;
  dia_semana_con_mas_retrasos: WeekdayRiskSummary | null;
  dia_semana_mas_probable: WeekdayRiskSummary | null;
  dia_semana_menos_probable: WeekdayRiskSummary | null;
}

export interface WeekMetrics extends DelayBuckets, PeriodExtremes {
  iso_year: number;
  iso_week: number;
  week_start: string;
  week_end: string;
  is_complete: boolean;
}

export interface MonthMetrics extends DelayBuckets, PeriodExtremes {
  year: number;
  month: number;
  is_complete: boolean;
}

export interface GlobalMetrics extends DelayBuckets {
  first_aggregated_date: string;
  significant_delay_threshold_minutes: number;
  dia_semana_mas_probable: WeekdayRiskSummary | null;
  franja_horaria_mas_probable: FranjaHorariaRiskSummary | null;
  tren_mas_probable: TrainMetrics | null;
}

export interface TrainSchedule {
  cod_comercial: string;
  sentido: string;
  hora_salida: string;
  hora_llegada_destino: string;
  weekdays: number[]; // 0=lunes .. 6=domingo
}

// ── Navegación del menú lateral ──────────────────────────────────────────
export type AppSection =
  | "seguimiento"
  | "horarios"
  | "estadisticas-trenes"
  | "estadisticas-tiempos"
  | "estadisticas-global";
