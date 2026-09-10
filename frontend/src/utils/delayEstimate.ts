// Aritmética de horas para la estimación de llegada de la pantalla de
// detalle del tren. La estadística (mediana y percentiles) la calcula la
// API a partir del histograma por minuto que guarda metrics_writer; aquí
// solo se convierte "hora programada + N minutos" en una hora de reloj.

/**
 * "18:47" + 12 -> "18:59". Envuelve por medianoche en ambos sentidos, así
 * que un tren nocturno con retraso muestra "00:05" y no "24:05", y un
 * percentil negativo (tren adelantado) sobre las 00:02 muestra "23:57".
 */
export function addMinutesToTime(time: string, minutes: number): string {
  const [hours, mins] = time.split(":").map(Number);
  const total = (((hours * 60 + mins + minutes) % 1440) + 1440) % 1440;
  const paddedHours = String(Math.floor(total / 60)).padStart(2, "0");
  const paddedMinutes = String(total % 60).padStart(2, "0");
  return `${paddedHours}:${paddedMinutes}`;
}
