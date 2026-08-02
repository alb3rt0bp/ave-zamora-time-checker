import { useEffect, useState } from "react";

const MADRID_TZ = "Europe/Madrid";

const dateFormatter = new Intl.DateTimeFormat("es-ES", {
  timeZone: MADRID_TZ,
  weekday: "long",
  year: "numeric",
  month: "long",
  day: "numeric",
});

// timeZoneName: "short" deja que Intl decida CET/CEST según la fecha (la
// IANA tz database ya gestiona el cambio de hora) — nunca se fija a mano,
// porque un rótulo "CEST" fijo mentiría media parte del año.
const timeFormatter = new Intl.DateTimeFormat("es-ES", {
  timeZone: MADRID_TZ,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  timeZoneName: "short",
});

export function Clock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const intervalId = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <p aria-label="Hora actual en España">
      {dateFormatter.format(now)} — {timeFormatter.format(now)}
    </p>
  );
}
