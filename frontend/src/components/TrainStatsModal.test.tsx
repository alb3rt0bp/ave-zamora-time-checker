import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { TrainMetrics, TrainSchedule } from "../types";
import { TrainStatsModal } from "./TrainStatsModal";

const SCHEDULE: TrainSchedule = {
  cod_comercial: "04154",
  sentido: "Madrid",
  hora_salida: "06:56",
  hora_llegada_destino: "08:56",
  weekdays: [0, 1, 2, 3, 4],
};

const METRICS: TrainMetrics = {
  cod_comercial: "04154",
  sentido: "Madrid",
  total_viajes: 10,
  viajes_bucket_puntual: 6,
  viajes_bucket_leve: 1,
  viajes_bucket_significativo: 2,
  viajes_bucket_grave: 1,
  pct_bucket_puntual: 60,
  pct_bucket_leve: 10,
  pct_bucket_significativo: 20,
  pct_bucket_grave: 10,
  viajes_retraso_significativo: 3,
  pct_retraso_significativo: 30,
  suma_retraso_significativo_minutos: 95,
  rank_retraso: 1,
  total_trenes_comparados: 22,
  // Muestra equivalente: mediana +7, habitual entre +1 y +14, P90 +25.
  estimacion_retraso: {
    mediana_minutos: 7,
    p25_minutos: 1,
    p75_minutos: 14,
    p90_minutos: 25,
    viajes_estimacion: 36,
    base: "tren",
  },
};

describe("TrainStatsModal", () => {
  it("renders the chart and summary when metrics are available", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: /04154/ })).toBeInTheDocument();
    expect(screen.getByText(/95 min/)).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    // Dos veces: la base de la estimación de llegada y los retrasos acumulados.
    expect(screen.getAllByText(/desde 31 de julio de 2026/)).toHaveLength(2);
  });

  it("shows the scheduled departure and arrival times next to the title", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Salida 06:56")).toBeInTheDocument();
    expect(screen.getByText(/Llegada 08:56/)).toBeInTheDocument();
  });

  it("shows the probable arrival time, its habitual range and the exceptional case", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    // Llegada programada 08:56 + mediana 7 min.
    expect(screen.getByText("09:03")).toBeInTheDocument();
    // P25 +1 y P75 +14 sobre la misma hora programada.
    expect(screen.getByText(/entre las 08:57 y las 09:10/)).toBeInTheDocument();
    // P90 +25.
    expect(screen.getByText(/más tarde de las 09:21/)).toBeInTheDocument();
    expect(screen.getByText(/36 viajes de este tren/)).toBeInTheDocument();
  });

  it("repeats the estimated delay next to the scheduled arrival", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    // Una vez en la cabecera, otra junto a la hora probable.
    expect(screen.getAllByText("+7 min")).toHaveLength(2);
  });

  it("says the estimate belongs to the sentido when the train has too few trips", () => {
    render(
      <TrainStatsModal
        codComercial="04505"
        schedule={SCHEDULE}
        metrics={{
          ...METRICS,
          estimacion_retraso: { ...METRICS.estimacion_retraso!, base: "sentido", viajes_estimacion: 395 },
        }}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/no tiene viajes suficientes/)).toBeInTheDocument();
    expect(screen.getByText(/395 viajes registrados en sentido/)).toBeInTheDocument();
  });

  it("omits the arrival estimate when there is no data to base it on", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={{ ...METRICS, estimacion_retraso: null }}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Llegada probable/)).not.toBeInTheDocument();
    // El resto del panel sigue en pie.
    expect(screen.getByText("30%")).toBeInTheDocument();
  });

  it("omits the arrival estimate when the schedule is unknown, since there is no time to add it to", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={undefined}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Llegada probable/)).not.toBeInTheDocument();
  });

  it("shows a punctual train's estimate without a fake positive delay", () => {
    render(
      <TrainStatsModal
        codComercial="04114"
        schedule={SCHEDULE}
        metrics={{
          ...METRICS,
          estimacion_retraso: {
            mediana_minutos: 0,
            p25_minutos: -2,
            p75_minutos: 3,
            p90_minutos: 7,
            viajes_estimacion: 41,
            base: "tren",
          },
        }}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Puntual")).toHaveLength(2);
    // P25 negativo: la llegada habitual empieza ANTES de la hora programada.
    expect(screen.getByText(/entre las 08:54 y las 08:59/)).toBeInTheDocument();
  });

  it("omits the schedule line when the train's schedule is unknown", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={undefined}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Salida/)).not.toBeInTheDocument();
  });

  it("omits the 'desde' clause when firstAggregatedDate is unknown", () => {
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate={undefined}
        thresholdMinutes={undefined}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/Retrasos significativos acumulados$/)).toBeInTheDocument();
  });

  it("shows an empty state when the train has no metrics yet", () => {
    render(
      <TrainStatsModal
        codComercial="99999"
        schedule={undefined}
        metrics={undefined}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/todavía no hay datos/i)).toBeInTheDocument();
  });

  it("calls onClose on close button, backdrop click, and Escape", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={onClose}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cerrar/i }));
    expect(onClose).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(2);

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("does not close when a key other than Escape is pressed", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={onClose}
      />,
    );

    await user.keyboard("{Enter}");

    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not close when clicking inside the sheet", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainStatsModal
        codComercial="04154"
        schedule={SCHEDULE}
        metrics={METRICS}
        firstAggregatedDate="2026-07-31"
        thresholdMinutes={15}
        onClose={onClose}
      />,
    );

    await user.click(screen.getByRole("heading", { name: /tren 04154/i }));

    expect(onClose).not.toHaveBeenCalled();
  });
});
