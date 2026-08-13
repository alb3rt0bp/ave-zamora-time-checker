import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("marks the active top-level section as current", () => {
    render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Seguimiento de trenes" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("keeps 'Estadísticas' collapsed by default when not on a stats section", () => {
    render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Por trenes" })).not.toBeInTheDocument();
  });

  it("starts expanded when the active section is already a stats page", () => {
    render(<Sidebar activeSection="estadisticas-global" onSelectSection={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Global" })).toHaveAttribute("aria-current", "page");
  });

  it("expands 'Estadísticas' on click, revealing its sub-pages", async () => {
    const user = userEvent.setup();
    render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Estadísticas" }));

    expect(screen.getByRole("button", { name: "Por trenes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Por tiempos" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Global" })).toBeInTheDocument();
  });

  it("calls onSelectSection with the right section when a sub-item is clicked", async () => {
    const user = userEvent.setup();
    const onSelectSection = vi.fn();
    render(<Sidebar activeSection="seguimiento" onSelectSection={onSelectSection} />);

    await user.click(screen.getByRole("button", { name: "Estadísticas" }));
    await user.click(screen.getByRole("button", { name: "Por tiempos" }));

    expect(onSelectSection).toHaveBeenCalledWith("estadisticas-tiempos");
  });

  it("calls onSelectSection with 'estadisticas-trenes' when 'Por trenes' is clicked", async () => {
    const user = userEvent.setup();
    const onSelectSection = vi.fn();
    render(<Sidebar activeSection="seguimiento" onSelectSection={onSelectSection} />);

    await user.click(screen.getByRole("button", { name: "Estadísticas" }));
    await user.click(screen.getByRole("button", { name: "Por trenes" }));

    expect(onSelectSection).toHaveBeenCalledWith("estadisticas-trenes");
  });

  it("calls onSelectSection when 'Seguimiento de trenes' is clicked", async () => {
    const user = userEvent.setup();
    const onSelectSection = vi.fn();
    render(<Sidebar activeSection="estadisticas-global" onSelectSection={onSelectSection} />);

    await user.click(screen.getByRole("button", { name: "Seguimiento de trenes" }));

    expect(onSelectSection).toHaveBeenCalledWith("seguimiento");
  });

  it("marks 'Horarios de trenes AVE' as current and calls onSelectSection when clicked", async () => {
    const user = userEvent.setup();
    const onSelectSection = vi.fn();
    render(<Sidebar activeSection="horarios" onSelectSection={onSelectSection} />);

    expect(screen.getByRole("button", { name: "Horarios de trenes AVE" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await user.click(screen.getByRole("button", { name: "Horarios de trenes AVE" }));

    expect(onSelectSection).toHaveBeenCalledWith("horarios");
  });

  describe("menú de hamburguesa (overlay en cualquier tamaño de pantalla)", () => {
    function asideEl(container: HTMLElement): HTMLElement {
      return container.querySelector(".app-sidebar") as HTMLElement;
    }

    it("starts closed, with no backdrop", () => {
      const { container } = render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

      expect(asideEl(container)).not.toHaveClass("app-sidebar--open");
      expect(container.querySelector(".sidebar-backdrop")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Abrir menú" })).toHaveAttribute("aria-expanded", "false");
    });

    it("opens on toggle click, showing the backdrop", async () => {
      const user = userEvent.setup();
      const { container } = render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

      await user.click(screen.getByRole("button", { name: "Abrir menú" }));

      expect(asideEl(container)).toHaveClass("app-sidebar--open");
      expect(container.querySelector(".sidebar-backdrop")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cerrar menú" })).toHaveAttribute("aria-expanded", "true");
    });

    it("closes again on a second toggle click", async () => {
      const user = userEvent.setup();
      const { container } = render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

      await user.click(screen.getByRole("button", { name: "Abrir menú" }));
      await user.click(screen.getByRole("button", { name: "Cerrar menú" }));

      expect(asideEl(container)).not.toHaveClass("app-sidebar--open");
    });

    it("closes when the backdrop is clicked", async () => {
      const user = userEvent.setup();
      const { container } = render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

      await user.click(screen.getByRole("button", { name: "Abrir menú" }));
      await user.click(container.querySelector(".sidebar-backdrop")!);

      expect(asideEl(container)).not.toHaveClass("app-sidebar--open");
    });

    it("stays open when a key other than Escape is pressed", async () => {
      const user = userEvent.setup();
      const { container } = render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

      await user.click(screen.getByRole("button", { name: "Abrir menú" }));
      await user.keyboard("{ArrowDown}");

      expect(asideEl(container)).toHaveClass("app-sidebar--open");
    });

    it("closes when Escape is pressed", async () => {
      const user = userEvent.setup();
      const { container } = render(<Sidebar activeSection="seguimiento" onSelectSection={vi.fn()} />);

      await user.click(screen.getByRole("button", { name: "Abrir menú" }));
      await user.keyboard("{Escape}");

      expect(asideEl(container)).not.toHaveClass("app-sidebar--open");
    });

    it("closes after selecting a top-level section", async () => {
      const user = userEvent.setup();
      const onSelectSection = vi.fn();
      const { container } = render(
        <Sidebar activeSection="estadisticas-global" onSelectSection={onSelectSection} />,
      );

      await user.click(screen.getByRole("button", { name: "Abrir menú" }));
      await user.click(screen.getByRole("button", { name: "Seguimiento de trenes" }));

      expect(onSelectSection).toHaveBeenCalledWith("seguimiento");
      expect(asideEl(container)).not.toHaveClass("app-sidebar--open");
    });

    it("closes after selecting a stats sub-page", async () => {
      const user = userEvent.setup();
      const onSelectSection = vi.fn();
      const { container } = render(<Sidebar activeSection="seguimiento" onSelectSection={onSelectSection} />);

      await user.click(screen.getByRole("button", { name: "Abrir menú" }));
      await user.click(screen.getByRole("button", { name: "Estadísticas" }));
      await user.click(screen.getByRole("button", { name: "Global" }));

      expect(onSelectSection).toHaveBeenCalledWith("estadisticas-global");
      expect(asideEl(container)).not.toHaveClass("app-sidebar--open");
    });
  });
});
