const DEFAULT_LATE_THRESHOLD_MIN = 10;
export const CLAIM_THRESHOLD_MIN = 15;

export function formatDelay(minutes: number | null): string {
  if (minutes === null) return "Sin datos";
  if (minutes === 0) return "Puntual";
  if (minutes > 0) return `+${minutes} min`;
  return `${minutes} min`;
}

export function isTrainLate(minutes: number | null, thresholdMin = DEFAULT_LATE_THRESHOLD_MIN): boolean {
  return minutes !== null && minutes > thresholdMin;
}

export function isCancelled(train: { cancelado?: boolean }): boolean {
  return !!train.cancelado;
}

export type DelayStatus = "ok" | "warn" | "danger" | "neutral";

// Nivel visual (pill de color) de un retraso: separado de isTrainLate porque
// aquí necesitamos 3 niveles (ok/warn/danger), no un simple booleano.
export function delayStatus(minutes: number | null, cancelado: boolean): DelayStatus {
  if (cancelado) return "danger";
  if (minutes === null) return "neutral";
  if (minutes > CLAIM_THRESHOLD_MIN) return "danger";
  if (minutes > DEFAULT_LATE_THRESHOLD_MIN) return "warn";
  return "ok";
}
