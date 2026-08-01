const MADRID_TZ = "Europe/Madrid";

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
