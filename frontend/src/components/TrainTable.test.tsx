import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TrainTable } from "./TrainTable";
import type { GlobalMetrics, RenfeTren, TrainMetrics, TrainRow, TrainSchedule } from "../types";

vi.mock("./TrainLiveModal", () => ({
  TrainLiveModal: ({ codComercial, onClose }: { codComercial: string; onClose: () => void }) => (
    <div role="dialog" aria-label={`mapa de ${codComercial}`}>
      <button type="button" onClick={onClose}>
        Cerrar
      </button>
    </div>
  ),
}));

vi.mock("./TrainStatsModal", () => ({
  TrainStatsModal: ({
    codComercial,
    metrics,
    firstAggregatedDate,
    thresholdMinutes,
    onClose,
  }: {
    codComercial: string;
    metrics: TrainMetrics | undefined;
    firstAggregatedDate: string | undefined;
    thresholdMinutes: number | undefined;
    onClose: () => void;
  }) => (
    <div role="dialog" aria-label={`detalle de ${codComercial}`}>
      <p>{`viajes: ${metrics?.total_viajes ?? "sin métricas"}`}</p>
      <p>{`desde: ${firstAggregatedDate ?? "-"} / umbral: ${thresholdMinutes ?? "-"}`}</p>
      <button type="button" onClick={onClose}>
        Cerrar
      </button>
    </div>
  ),
}));

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

const schedule: Map<string, TrainSchedule> = new Map([
  [
    "04154",
    {
      cod_comercial: "04154",
      sentido: "Madrid",
      hora_salida: "06:35",
      hora_llegada_destino: "08:35",
      weekdays: [0, 1, 2, 3, 4],
    },
  ],
]);

describe("TrainTable", () => {
  it("renders one row per train with its key fields", () => {
    render(<TrainTable rows={rows} schedule={schedule} />);

    expect(screen.getByText("04154")).toBeInTheDocument();
    expect(screen.getByText("Madrid")).toBeInTheDocument();
    expect(screen.getByText("06:35")).toBeInTheDocument();
    expect(screen.getByText("07:41")).toBeInTheDocument();
    expect(screen.getByText("07:03")).toBeInTheDocument();
    expect(screen.getByText("+6 min")).toBeInTheDocument();
  });

  it("shows a dash for hora de salida when the train isn't in the schedule index", () => {
    render(<TrainTable rows={rows} />);

    const row04154 = screen.getByText("04154").closest("tr")!;
    expect(within(row04154).getAllByText("-").length).toBeGreaterThan(0);
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

  it("labels the columns as requested: sentido, salida, llegada, llegada corregida and paso por Zamora", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.getByRole("columnheader", { name: "Sentido" })).toBeInTheDocument();
    expect(screen.getByText("Hora de salida")).toBeInTheDocument();
    expect(screen.getByText("Hora de llegada")).toBeInTheDocument();
    expect(screen.getByText("Llegada corregida")).toBeInTheDocument();
    expect(screen.getByText("Hora de paso por Zamora")).toBeInTheDocument();
  });

  it("does not show claim buttons when the delay is 15 minutes or less", () => {
    render(<TrainTable rows={rows} />);

    expect(screen.queryByRole("button", { name: /reclamar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /posible indemnización/i })).not.toBeInTheDocument();
  });

  it("shows a 'Reclamar' button when the delay is greater than 15 minutes", () => {
    const rowsWithDelay: TrainRow[] = [
      { codComercial: "04300", sentido: "Madrid", horaProgramada: "10:00", horaLlegada: "10:20", horaPasoZamora: "09:00", retrasoMinutos: 20, cancelado: false },
    ];

    render(<TrainTable rows={rowsWithDelay} />);

    expect(screen.getByRole("button", { name: /📝 Reclamar/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /posible indemnización/i })).not.toBeInTheDocument();
  });

  it("also shows a 'Posible indemnización' button when the delay is greater than 60 minutes", () => {
    const rowsWithBigDelay: TrainRow[] = [
      { codComercial: "04400", sentido: "Madrid", horaProgramada: "11:00", horaLlegada: "12:05", horaPasoZamora: "10:00", retrasoMinutos: 65, cancelado: false },
    ];

    render(<TrainTable rows={rowsWithBigDelay} />);

    expect(screen.getByRole("button", { name: /📝 Reclamar/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /💶 Posible indemnización/ })).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: /💶 Posible indemnización/ }));

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
    expect(screen.queryByRole("button", { name: /posible indemnización/i })).not.toBeInTheDocument();
  });

  it("renders the header and data cells inside the styled table card", () => {
    const { container } = render(<TrainTable rows={rows} />);

    expect(container.querySelector(".table-card")).toBeInTheDocument();
    expect(container.querySelector(".train-table")).toBeInTheDocument();
    const cells = [...screen.getAllByRole("columnheader"), ...screen.getAllByRole("cell")];
    expect(cells.length).toBeGreaterThan(0);
  });

  describe("live position link", () => {
    const flotaWith04154: Map<string, RenfeTren> = new Map([
      ["04154", { codComercial: "04154", latitud: 41.5, longitud: -5.74 }],
    ]);

    it("renders the train code as a clickable link when a live position is available", () => {
      render(<TrainTable rows={rows} flota={flotaWith04154} />);

      expect(screen.getByRole("button", { name: "04154" })).toBeInTheDocument();
    });

    it("opens the map modal for the clicked train", () => {
      render(<TrainTable rows={rows} flota={flotaWith04154} />);

      fireEvent.click(screen.getByRole("button", { name: "04154" }));

      expect(screen.getByRole("dialog", { name: "mapa de 04154" })).toBeInTheDocument();
    });

    it("closes the map modal when it reports onClose", () => {
      render(<TrainTable rows={rows} flota={flotaWith04154} />);

      fireEvent.click(screen.getByRole("button", { name: "04154" }));
      fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("does not render a modal when no train has been clicked", () => {
      render(<TrainTable rows={rows} flota={flotaWith04154} />);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // La posición en vivo solo la pasa la vista de hoy: en un día ya volcado
    // el mismo tren circulando ahora no es el viaje que se está consultando.
    it("does not link to the map when the view provides no live positions", () => {
      render(<TrainTable rows={rows} />);

      fireEvent.click(screen.getByRole("button", { name: "04154" }));

      expect(screen.queryByRole("dialog", { name: "mapa de 04154" })).not.toBeInTheDocument();
      expect(screen.getByRole("dialog", { name: "detalle de 04154" })).toBeInTheDocument();
    });
  });

  describe("train detail modal", () => {
    const flotaWith04154: Map<string, RenfeTren> = new Map([
      ["04154", { codComercial: "04154", latitud: 41.5, longitud: -5.74 }],
    ]);

    const metrics: Map<string, TrainMetrics> = new Map([
      [
        "04154",
        {
          cod_comercial: "04154",
          sentido: "Madrid",
          rank_retraso: 3,
          total_trenes_comparados: 54,
          estimacion_retraso: null,
          total_viajes: 42,
          viajes_bucket_puntual: 20,
          viajes_bucket_leve: 12,
          viajes_bucket_significativo: 7,
          viajes_bucket_grave: 3,
          pct_bucket_puntual: 47.6,
          pct_bucket_leve: 28.6,
          pct_bucket_significativo: 16.7,
          pct_bucket_grave: 7.1,
          viajes_retraso_significativo: 10,
          pct_retraso_significativo: 23.8,
          suma_retraso_significativo_minutos: 214,
        },
      ],
    ]);

    const globalMetrics = {
      first_aggregated_date: "2026-07-30",
      significant_delay_threshold_minutes: 15,
    } as GlobalMetrics;

    it("opens the detail modal for a train without live position", () => {
      render(<TrainTable rows={rows} flota={flotaWith04154} />);

      fireEvent.click(screen.getByRole("button", { name: "04200" }));

      expect(screen.getByRole("dialog", { name: "detalle de 04200" })).toBeInTheDocument();
    });

    it("passes the train's metrics and the global context to the modal", () => {
      render(<TrainTable rows={rows} metrics={metrics} globalMetrics={globalMetrics} />);

      fireEvent.click(screen.getByRole("button", { name: "04154" }));

      expect(screen.getByText("viajes: 42")).toBeInTheDocument();
      expect(screen.getByText("desde: 2026-07-30 / umbral: 15")).toBeInTheDocument();
    });

    it("still opens the modal for a train with no metrics aggregated yet", () => {
      render(<TrainTable rows={rows} metrics={metrics} globalMetrics={globalMetrics} />);

      fireEvent.click(screen.getByRole("button", { name: "04200" }));

      expect(screen.getByText("viajes: sin métricas")).toBeInTheDocument();
    });

    it("closes the detail modal when it reports onClose", () => {
      render(<TrainTable rows={rows} />);

      fireEvent.click(screen.getByRole("button", { name: "04154" }));
      fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // El sondeo de flotaLD.json refresca cada 15s: un tren puede salir de la
    // flota con su mapa ya abierto, y eso no debe cambiar la modal visible.
    it("keeps the open map modal even if the train leaves the live fleet", () => {
      const { rerender } = render(<TrainTable rows={rows} flota={flotaWith04154} />);
      fireEvent.click(screen.getByRole("button", { name: "04154" }));

      rerender(<TrainTable rows={rows} flota={new Map()} />);

      expect(screen.getByRole("dialog", { name: "mapa de 04154" })).toBeInTheDocument();
    });
  });
});
