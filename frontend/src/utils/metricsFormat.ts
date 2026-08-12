// Formato para las páginas de Estadísticas: nombres de día de la semana y
// franja horaria en español, y las etiquetas de los 4 tramos de retraso del
// gráfico de tipo queso. No reutiliza dia_semana de DayTrain (ese es un
// strftime("%A") en inglés del backend, sin relación con estos campos
// numéricos 0-6 de las métricas).

const WEEKDAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export function formatWeekday(dayIndex: number): string {
  return WEEKDAY_NAMES[dayIndex] ?? "?";
}

const FRANJA_LABELS: Record<string, string> = {
  manana: "Mañana (06-14h)",
  tarde: "Tarde (14-20h)",
  noche: "Noche (20-06h)",
};

export function formatFranjaHoraria(franja: string): string {
  return FRANJA_LABELS[franja] ?? franja;
}

const SPANISH_DATE_FORMATTER = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

/** "2026-07-31" -> "31 de julio de 2026". timeZone: UTC evita que un huso
 * horario negativo del navegador reste un día a una fecha "YYYY-MM-DD" pura. */
export function formatSpanishDate(dateIso: string): string {
  return SPANISH_DATE_FORMATTER.format(new Date(`${dateIso}T00:00:00Z`));
}

const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

/** "2026-07-31" -> "31 jul" (para el selector de semanas de "Por tiempos"). */
export function formatShortDate(dateIso: string): string {
  return SHORT_DATE_FORMATTER.format(new Date(`${dateIso}T00:00:00Z`));
}

export const MONTH_NAMES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

/** month es 1-12 (como en la respuesta de /metrics/months). */
export function formatMonthName(month: number): string {
  return MONTH_NAMES[month - 1] ?? "?";
}

export const DELAY_BUCKET_ORDER = ["puntual", "leve", "significativo", "grave"] as const;
export type DelayBucketKey = (typeof DELAY_BUCKET_ORDER)[number];

// thresholdMinutes es SIGNIFICANT_DELAY_THRESHOLD_MINUTES (configurable en
// el backend, expuesto en /metrics/global): el límite entre "leve" y
// "significativo" depende de su valor real, no de un 15 fijo en el
// frontend. Por defecto 15 (el valor con el que se ha desplegado siempre
// hasta ahora) para las páginas que no cargan /metrics/global.
export function formatDelayBucketLabel(bucket: DelayBucketKey, thresholdMinutes = 15): string {
  switch (bucket) {
    case "puntual":
      return "< 5 min";
    case "leve":
      return `5-${thresholdMinutes} min`;
    case "significativo":
      return `${thresholdMinutes}-60 min`;
    case "grave":
      return "> 60 min";
  }
}
