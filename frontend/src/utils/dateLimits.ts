const MADRID_TZ = "Europe/Madrid";

/** Suma (o resta, con delta negativo) días a una fecha "YYYY-MM-DD", en UTC
 * para no arrastrar desplazamientos por huso horario del entorno. */
export function addDaysIso(dateIso: string, delta: number): string {
  const [year, month, day] = dateIso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}

export function yesterdayMadrid(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: MADRID_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);

  const get = (type: string) => parts.find((part) => part.type === type)!.value;
  const todayMadridUtc = new Date(
    Date.UTC(Number(get("year")), Number(get("month")) - 1, Number(get("day"))),
  );
  todayMadridUtc.setUTCDate(todayMadridUtc.getUTCDate() - 1);

  return todayMadridUtc.toISOString().slice(0, 10);
}
