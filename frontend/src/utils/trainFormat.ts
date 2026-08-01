const DEFAULT_LATE_THRESHOLD_MIN = 10;

export function formatDelay(minutes: number | null): string {
  if (minutes === null) return "Sin datos";
  if (minutes === 0) return "Puntual";
  return `+${minutes} min`;
}

export function isTrainLate(minutes: number | null, thresholdMin = DEFAULT_LATE_THRESHOLD_MIN): boolean {
  return minutes !== null && minutes > thresholdMin;
}

export function isCancelled(train: { cancelado?: boolean }): boolean {
  return !!train.cancelado;
}
