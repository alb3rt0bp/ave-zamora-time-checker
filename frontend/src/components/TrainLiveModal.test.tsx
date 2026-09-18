import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RenfeTren, TrainMetrics, TrainSchedule } from "../types";
import { TrainLiveModal } from "./TrainLiveModal";

// Mismo stub que TrainMapModal.test.tsx: jsdom no calcula layout real, así
// que se sustituyen Marker/useMap por dobles inertes, suficientes para que
// TrainMapFace pueda montarse dentro de esta modal combinada.
vi.mock("react-leaflet", async () => {
  const actual = await vi.importActual<typeof import("react-leaflet")>("react-leaflet");
  return {
    ...actual,
    Marker: () => <div data-testid="marker" />,
    useMap: () => ({ flyTo: vi.fn() }),
  };
});

function flotaWith(train: RenfeTren): Map<string, RenfeTren> {
  return new Map([[train.codComercial, train]]);
}

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
  estimacion_retraso: null,
};

const baseProps = {
  codComercial: "04154",
  sentido: "Madrid",
  horaSalida: "07:41",
  horaLlegada: "08:56",
  retrasoMinutos: 6,
  cancelado: false,
  schedule: SCHEDULE,
  metrics: METRICS,
  firstAggregatedDate: "2026-07-31",
  thresholdMinutes: 15,
};

describe("TrainLiveModal", () => {
  it("opens on the map face by default", () => {
    render(
      <TrainLiveModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: /04154/ })).toBeInTheDocument();
    expect(screen.getByTestId("marker")).toBeInTheDocument();
    expect(screen.queryByText(/riesgo de retraso/i)).not.toBeInTheDocument();
  });

  it("flips to the detail face when the flip button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <TrainLiveModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /ver el detalle del tren/i }));

    await waitFor(() => expect(screen.getByText(/riesgo de retraso/i)).toBeInTheDocument());
    expect(screen.queryByTestId("marker")).not.toBeInTheDocument();
  });

  it("flips back to the map from the detail face", async () => {
    const user = userEvent.setup();
    render(
      <TrainLiveModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /ver el detalle del tren/i }));
    await waitFor(() => expect(screen.getByText(/riesgo de retraso/i)).toBeInTheDocument());
    // El botón de volteo queda deshabilitado mientras dura la animación (ver
    // isFlipping en TrainLiveModal.tsx): hay que esperar a que se reactive
    // antes de poder pulsarlo de nuevo para volver al mapa.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /ver la posición en el mapa/i })).toBeEnabled(),
    );

    await user.click(screen.getByRole("button", { name: /ver la posición en el mapa/i }));
    await waitFor(() => expect(screen.getByTestId("marker")).toBeInTheDocument());
  });

  it("closes on close button, backdrop click and Escape", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainLiveModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
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

  it("renders nothing when the train leaves the fleet while on the map face", () => {
    const { container } = render(<TrainLiveModal {...baseProps} flota={new Map()} onClose={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });
});
