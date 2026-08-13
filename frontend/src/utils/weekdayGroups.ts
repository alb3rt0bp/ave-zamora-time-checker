export interface WeekdayGroup {
  key: string;
  label: string;
  days: number[]; // 0=lunes .. 6=domingo
}

// Grupos de tipo de día compartidos por "Por trenes" y "Horarios de trenes
// AVE": lunes-viernes se agrupan bajo "Laborables" (mismo horario todos los
// días laborables); sábado y domingo mantienen apartado propio porque sí
// pueden divergir.
export const WEEKDAY_GROUPS: WeekdayGroup[] = [
  { key: "laborables", label: "Laborables", days: [0, 1, 2, 3, 4] },
  { key: "sabado", label: "Sábado", days: [5] },
  { key: "domingo", label: "Domingo", days: [6] },
];

interface ScheduledTrain {
  cod_comercial: string;
  weekdays: number[];
  hora_salida: string;
}

// Agrupa por tipo de día sin duplicar un mismo tren dentro de un grupo
// aunque corra varios días de ese grupo (p.ej. un tren laborable con
// weekdays [0,1,2,3,4] solo aparece una vez bajo "Laborables"). Cada grupo
// queda ordenado por hora de salida.
export function groupByWeekdayGroup<T extends ScheduledTrain>(trains: T[]): Map<string, T[]> {
  const groups = new Map<string, T[]>();
  for (const group of WEEKDAY_GROUPS) {
    const seenCodes = new Set<string>();
    const matched: T[] = [];
    for (const train of trains) {
      if (!seenCodes.has(train.cod_comercial) && train.weekdays.some((day) => group.days.includes(day))) {
        seenCodes.add(train.cod_comercial);
        matched.push(train);
      }
    }
    if (matched.length > 0) {
      matched.sort((a, b) => a.hora_salida.localeCompare(b.hora_salida));
      groups.set(group.key, matched);
    }
  }
  return groups;
}
