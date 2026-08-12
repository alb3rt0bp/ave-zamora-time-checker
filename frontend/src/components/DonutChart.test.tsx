import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DonutChart } from "./DonutChart";
import type { DelayBuckets } from "../types";

const BUCKETS: DelayBuckets = {
  total_viajes: 20,
  viajes_bucket_puntual: 10,
  viajes_bucket_leve: 5,
  viajes_bucket_significativo: 3,
  viajes_bucket_grave: 2,
  pct_bucket_puntual: 50,
  pct_bucket_leve: 25,
  pct_bucket_significativo: 15,
  pct_bucket_grave: 10,
  viajes_retraso_significativo: 5,
  pct_retraso_significativo: 25,
  suma_retraso_significativo_minutos: 180,
};

describe("DonutChart", () => {
  it("shows the total trip count in the center", () => {
    render(<DonutChart buckets={BUCKETS} />);

    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("viajes")).toBeInTheDocument();
  });

  it("renders a legend row with label and percentage for every bucket", () => {
    render(<DonutChart buckets={BUCKETS} />);

    expect(screen.getByText("< 5 min")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("5-15 min")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(screen.getByText("15-60 min")).toBeInTheDocument();
    expect(screen.getByText("15%")).toBeInTheDocument();
    expect(screen.getByText("> 60 min")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
  });

  it("reflects a custom threshold in the leve/significativo boundary labels", () => {
    render(<DonutChart buckets={BUCKETS} thresholdMinutes={20} />);

    expect(screen.getByText("5-20 min")).toBeInTheDocument();
    expect(screen.getByText("20-60 min")).toBeInTheDocument();
  });

  it("provides a screen-reader-only textual summary of every bucket", () => {
    render(<DonutChart buckets={BUCKETS} />);

    expect(
      screen.getByText(/Distribución de 20 viajes por tramo de retraso/),
    ).toBeInTheDocument();
  });
});
