import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

  it("does not show claim buttons when the delay is 15 minutes or less", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.queryByRole("button", { name: /reclamar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /posible reclamación/i })).not.toBeInTheDocument();
  });

  it("shows a 'Reclamar' button when the delay is greater than 15 minutes", () => {
    const rowsWithDelay: TrainRow[] = [
      { codComercial: "04300", sentido: "Madrid", horaProgramada: "10:00", horaLlegada: "10:20", horaPasoZamora: "09:00", retrasoMinutos: 20, cancelado: false },
    ];

    render(<TrainTable rows={rowsWithDelay} />);

    expect(screen.getByRole("button", { name: /📝 Reclamar/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /posible reclamación/i })).not.toBeInTheDocument();
  });

  it("also shows a 'Posible reclamación' button when the delay is greater than 60 minutes", () => {
    const rowsWithBigDelay: TrainRow[] = [
      { codComercial: "04400", sentido: "Madrid", horaProgramada: "11:00", horaLlegada: "12:05", horaPasoZamora: "10:00", retrasoMinutos: 65, cancelado: false },
    ];

    render(<TrainTable rows={rowsWithBigDelay} />);

    expect(screen.getByRole("button", { name: /📝 Reclamar/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /💶 Posible reclamación/ })).toBeInTheDocument();
  });

  it("opens the claim button in a new tab pointing at the Renfe claim form", () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const rowsWithDelay: TrainRow[] = [
      { codComercial: "04300", sentido: "Madrid", horaProgramada: "10:00", horaLlegada: "10:20", horaPasoZamora: "09:00", retrasoMinutos: 20, cancelado: false },
    ];

    render(<TrainTable rows={rowsWithDelay} />);
    fireEvent.click(screen.getByRole("button", { name: /📝 Reclamar/ }));

    expect(openSpy).toHaveBeenCalledWith(
      "https://venta.renfe.com/vol/petitionPersonalData.do?petition_personal_data_origin=CLAIM",
      "_blank",
      "noopener,noreferrer",
    );

    openSpy.mockRestore();
  });

  it("opens the possible-claim button in a new tab pointing at the Renfe punctuality commitment page", () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const rowsWithBigDelay: TrainRow[] = [
      { codComercial: "04400", sentido: "Madrid", horaProgramada: "11:00", horaLlegada: "12:05", horaPasoZamora: "10:00", retrasoMinutos: 65, cancelado: false },
    ];

    render(<TrainTable rows={rowsWithBigDelay} />);
    fireEvent.click(screen.getByRole("button", { name: /💶 Posible reclamación/ }));

    expect(openSpy).toHaveBeenCalledWith(
      "https://www.renfe.com/es/es/ayuda/compromiso-puntualidad",
      "_blank",
      "noopener,noreferrer",
    );

    openSpy.mockRestore();
  });

  it("does not show claim buttons for a cancelled train even with a stale delay value", () => {
    const cancelledWithDelay: TrainRow[] = [
      { codComercial: "04500", sentido: "Madrid", horaProgramada: "12:00", horaLlegada: null, horaPasoZamora: null, retrasoMinutos: 90, cancelado: true },
    ];

    render(<TrainTable rows={cancelledWithDelay} />);

    expect(screen.queryByRole("button", { name: /reclamar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /posible reclamación/i })).not.toBeInTheDocument();
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
