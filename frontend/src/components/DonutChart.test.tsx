import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DonutChart, DonutTooltip } from "./DonutChart";
import type { DelayBuckets } from "../types";

type DonutTooltipProps = Parameters<typeof DonutTooltip>[0];

function tooltipProps(props: { active: boolean; payload: unknown[] }): DonutTooltipProps {
  return props as unknown as DonutTooltipProps;
}

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

  it("renders without error when only one bucket has data", () => {
    const singleBucket: DelayBuckets = {
      ...BUCKETS,
      total_viajes: 10,
      viajes_bucket_puntual: 10,
      viajes_bucket_leve: 0,
      viajes_bucket_significativo: 0,
      viajes_bucket_grave: 0,
      pct_bucket_puntual: 100,
      pct_bucket_leve: 0,
      pct_bucket_significativo: 0,
      pct_bucket_grave: 0,
    };

    render(<DonutChart buckets={singleBucket} />);

    expect(screen.getByText("10")).toBeInTheDocument();
  });
});

describe("DonutTooltip", () => {
  it("renders nothing when inactive", () => {
    const { container } = render(<DonutTooltip {...tooltipProps({ active: false, payload: [] })} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when there is no payload", () => {
    const { container } = render(<DonutTooltip {...tooltipProps({ active: true, payload: [] })} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the payload entry has no slice data", () => {
    const { container } = render(<DonutTooltip {...tooltipProps({ active: true, payload: [{}] })} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("shows the slice value and percentage when active", () => {
    render(
      <DonutTooltip
        {...tooltipProps({
          active: true,
          payload: [
            {
              payload: { key: "puntual", label: "< 5 min", value: 10, pct: 50, color: "var(--status-ok)" },
            },
          ],
        })}
      />,
    );

    expect(screen.getByText("10 viajes")).toBeInTheDocument();
    expect(screen.getByText("< 5 min · 50%")).toBeInTheDocument();
  });
});
