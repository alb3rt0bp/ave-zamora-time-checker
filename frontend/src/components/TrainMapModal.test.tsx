import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RenfeTren } from "../types";
import { TrainMapModal } from "./TrainMapModal";

// jsdom no calcula layout real (el contenedor del mapa mide 0x0), así que
// leaflet nunca proyecta una posición de píxel concreta para el marcador:
// se sustituye Marker por un stub que expone su prop `position` tal cual,
// para poder comprobar que se actualiza al refrescarse la flota.
vi.mock("react-leaflet", async () => {
  const actual = await vi.importActual<typeof import("react-leaflet")>("react-leaflet");
  return {
    ...actual,
    Marker: ({ position }: { position: [number, number] }) => (
      <div data-testid="marker" data-position={JSON.stringify(position)} />
    ),
  };
});

function flotaWith(train: RenfeTren): Map<string, RenfeTren> {
  return new Map([[train.codComercial, train]]);
}

describe("TrainMapModal", () => {
  it("renders a dialog naming the selected train", () => {
    render(
      <TrainMapModal
        codComercial="04154"
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: /04154/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /tren 04154/i })).toBeInTheDocument();
  });

  it("renders nothing when the train is no longer in the fleet", () => {
    const { container } = render(
      <TrainMapModal codComercial="04154" flota={new Map()} onClose={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("calls onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TrainMapModal
        codComercial="04154"
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
        codComercial="04154"
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
        codComercial="04154"
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
        codComercial="04154"
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
        codComercial="04154"
        flota={flotaWith({ codComercial: "04154", latitud: 41.5, longitud: -5.74 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId("marker")).toHaveAttribute("data-position", JSON.stringify([41.5, -5.74]));

    rerender(
      <TrainMapModal
        codComercial="04154"
        flota={flotaWith({ codComercial: "04154", latitud: 43.0, longitud: -8.0 })}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByTestId("marker")).toHaveAttribute("data-position", JSON.stringify([43.0, -8.0]));
  });
});
