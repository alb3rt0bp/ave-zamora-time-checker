import { http, HttpResponse } from "msw";

const API_BASE_URL = "http://localhost:3000";

export const handlers = [
  http.get(`${API_BASE_URL}/trains/today`, () => HttpResponse.json([])),
  http.get(`${API_BASE_URL}/trains/:date`, () =>
    HttpResponse.json({ error: "no hay datos para esa fecha todavía" }, { status: 404 }),
  ),
];
