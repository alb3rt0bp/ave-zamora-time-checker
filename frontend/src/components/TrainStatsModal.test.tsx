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
    expect(screen.getByText(/desde 31 de julio de 2026/)).toBeInTheDocument();
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
    expect(screen.getByText("Llegada 08:56")).toBeInTheDocument();
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
