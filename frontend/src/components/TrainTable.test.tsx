import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrainTable } from "./TrainTable";
import type { TrainRow } from "../types";

const rows: TrainRow[] = [
  {
    codComercial: "04154",
    sentido: "Madrid",
    horaProgramada: "07:41",
    horaLlegada: "07:47",
    retrasoMinutos: 6,
    cancelado: false,
  },
  {
    codComercial: "04200",
    sentido: "Galicia",
    horaProgramada: "08:00",
    horaLlegada: null,
    retrasoMinutos: null,
    cancelado: true,
  },
];

describe("TrainTable", () => {
  it("renders one row per train with its key fields", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.getByText("04154")).toBeInTheDocument();
    expect(screen.getByText("Madrid")).toBeInTheDocument();
    expect(screen.getByText("07:41")).toBeInTheDocument();
    expect(screen.getByText("+6 min")).toBeInTheDocument();
  });

  it("shows a cancelled indicator for cancelled trains", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.getByText("Cancelado")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no trains", () => {
    render(<TrainTable rows={[]} />);

    expect(screen.getByText(/no hay trenes/i)).toBeInTheDocument();
  });
});
