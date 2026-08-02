import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrainTable } from "./TrainTable";
import type { TrainRow } from "../types";

const rows: TrainRow[] = [
  {
    codComercial: "04154",
    sentido: "Madrid",
    horaProgramada: "07:41",
    horaLlegada: "07:47",
    horaPasoZamora: "07:03",
    retrasoMinutos: 6,
    cancelado: false,
  },
  {
    codComercial: "04200",
    sentido: "Galicia",
    horaProgramada: "08:00",
    horaLlegada: null,
    horaPasoZamora: null,
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
    expect(screen.getByText("07:03")).toBeInTheDocument();
    expect(screen.getByText("+6 min")).toBeInTheDocument();
  });

  it("shows a dash for hora de paso por Zamora when it hasn't been captured yet", () => {
    const rowsWithPending: TrainRow[] = [
      ...rows,
      {
        codComercial: "04999",
        sentido: "Madrid",
        horaProgramada: "09:00",
        horaLlegada: null,
        horaPasoZamora: null,
        retrasoMinutos: null,
        cancelado: false,
      },
    ];

    render(<TrainTable rows={rowsWithPending} />);

    const pendingRow = screen.getByText("04999").closest("tr")!;
    expect(within(pendingRow).getAllByText("-")).not.toHaveLength(0);
  });

  it("shows a cancelled indicator for cancelled trains", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.getByText("Cancelado")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no trains", () => {
    render(<TrainTable rows={[]} />);

    expect(screen.getByText(/no hay trenes/i)).toBeInTheDocument();
  });

  it("sorts rows by hora programada ascending, regardless of input order", () => {
    const unsorted: TrainRow[] = [
      { codComercial: "B", sentido: "Madrid", horaProgramada: "09:00", horaLlegada: null, horaPasoZamora: null, retrasoMinutos: null, cancelado: false },
      { codComercial: "A", sentido: "Madrid", horaProgramada: "07:00", horaLlegada: null, horaPasoZamora: null, retrasoMinutos: null, cancelado: false },
      { codComercial: "C", sentido: "Madrid", horaProgramada: "08:00", horaLlegada: null, horaPasoZamora: null, retrasoMinutos: null, cancelado: false },
    ];

    render(<TrainTable rows={unsorted} />);

    const dataRows = screen.getAllByRole("row").slice(1);
    const codes = dataRows.map((row) => within(row).getAllByRole("cell")[0].textContent);
    expect(codes).toEqual(["A", "C", "B"]);
  });

  it("labels the arrival column as 'Hora de llegada corregida'", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.getByText("Hora de llegada corregida")).toBeInTheDocument();
    expect(screen.queryByText("Hora llegada")).not.toBeInTheDocument();
  });

  it("labels the Zamora passage column as 'Hora de paso por Zamora'", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.getByText("Hora de paso por Zamora")).toBeInTheDocument();
  });

  it("applies a border to every table cell", () => {
    render(<TrainTable rows={rows} />);

    const cells = [...screen.getAllByRole("columnheader"), ...screen.getAllByRole("cell")];
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach((cell) => {
      expect(cell).toHaveStyle({ border: "1px solid #ccc" });
    });
  });
});
