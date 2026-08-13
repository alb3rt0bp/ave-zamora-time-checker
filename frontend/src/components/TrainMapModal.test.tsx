import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RenfeTren } from "../types";
import { TrainMapModal } from "./TrainMapModal";

// jsdom no calcula layout real (el contenedor del mapa mide 0x0), así que
// leaflet nunca proyecta una posición de píxel concreta para el marcador:
// se sustituye Marker por un stub que expone su prop `position` (y el html
// del icono, para comprobar la orientación del emoji) tal cual, y useMap
// por un stub cuyo flyTo se puede espiar para comprobar la animación de
// acercamiento inicial.
const { flyToSpy } = vi.hoisted(() => ({ flyToSpy: vi.fn() }));

vi.mock("react-leaflet", async () => {
  const actual = await vi.importActual<typeof import("react-leaflet")>("react-leaflet");
  return {
    ...actual,
    Marker: ({ position, icon }: { position: [number, number]; icon?: { options?: { html?: string } } }) => (
      <div
        data-testid="marker"
        data-position={JSON.stringify(position)}
        data-icon-html={icon?.options?.html ?? ""}
      />
    ),
    useMap: () => ({ flyTo: flyToSpy }),
  };
});

function flotaWith(train: RenfeTren): Map<string, RenfeTren> {
  return new Map([[train.codComercial, train]]);
}

const baseProps = {
  codComercial: "04154",
  sentido: "Madrid",
  horaSalida: "07:41",
  horaLlegada: "08:56",
  retrasoMinutos: 6,
  cancelado: false,
};

describe("TrainMapModal", () => {
  it("renders a dialog naming the selected train", () => {
    render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: /04154/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /tren 04154/i })).toBeInTheDocument();
  });

  it("shows sentido, scheduled times and delay next to the train code", () => {
    render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Madrid")).toBeInTheDocument();
    expect(screen.getByText("Salida 07:41")).toBeInTheDocument();
    expect(screen.getByText("Llegada 08:56")).toBeInTheDocument();
    expect(screen.getByText("+6 min")).toBeInTheDocument();
  });

  it("does not show a delay pill for a cancelled train", () => {
    render(
      <TrainMapModal
        {...baseProps}
        cancelado
        retrasoMinutos={null}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText("Sin datos")).not.toBeInTheDocument();
  });

  it("renders nothing when the train is no longer in the fleet", () => {
    const { container } = render(<TrainMapModal {...baseProps} flota={new Map()} onClose={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("calls onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={onClose}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cerrar/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={onClose}
      />,
    );

    await user.click(screen.getByRole("dialog"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when clicking inside the modal content", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={onClose}
      />,
    );

    await user.click(screen.getByRole("heading", { name: /tren 04154/i }));

    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose when Escape is pressed", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={onClose}
      />,
    );

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("moves the marker when the fleet data refreshes with a new position", () => {
    const { rerender } = render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId("marker")).toHaveAttribute("data-position", JSON.stringify([41.5, -5.74]));

    rerender(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 43.0, longitud: -8.0 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId("marker")).toHaveAttribute("data-position", JSON.stringify([43.0, -8.0]));
  });

  it("animates the map into the target scale on load", () => {
    flyToSpy.mockClear();

    render(
      <TrainMapModal
        {...baseProps}
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(flyToSpy).toHaveBeenCalledTimes(1);
    expect(flyToSpy).toHaveBeenCalledWith([41.5, -5.74], expect.any(Number), expect.any(Object));
  });

  it("uses a train emoji marker pointing right for Madrid-bound trains", () => {
    render(
      <TrainMapModal
        {...baseProps}
        sentido="Madrid"
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    const html = screen.getByTestId("marker").getAttribute("data-icon-html") ?? "";
    expect(html).toContain("🚄");
    expect(html).toContain("train-marker-icon__glyph--right");
  });

  it("uses a train emoji marker pointing left for Galicia-bound trains", () => {
    render(
      <TrainMapModal
        {...baseProps}
        sentido="Galicia"
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    const html = screen.getByTestId("marker").getAttribute("data-icon-html") ?? "";
    expect(html).toContain("🚄");
    expect(html).not.toContain("train-marker-icon__glyph--right");
  });
});
