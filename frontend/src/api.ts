import type { DayTrain, RenfeTren, TodayTrain } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class NotFoundError extends Error {}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (response.status === 404) {
    throw new NotFoundError(`No hay datos disponibles: ${path}`);
  }
  if (!response.ok) {
    throw new Error(`La petición a ${path} falló con estado ${response.status}`);
  }
  return response.json();
}

export function fetchToday(): Promise<TodayTrain[]> {
  return fetchJson<TodayTrain[]>("/trains/today");
}

export function fetchByDate(dateIso: string): Promise<DayTrain[]> {
  return fetchJson<DayTrain[]>(`/trains/${dateIso}`);
}

interface RenfeFlotaResponse {
  fechaActualizacion: string;
  trenes: RenfeTren[];
}

export function fetchRenfeFlota(): Promise<RenfeTren[]> {
  return fetchJson<RenfeFlotaResponse>("/renfe/flota").then((data) => data.trenes);
}
