import { useEffect, useState } from "react";
import { ChevronRightIcon, MenuIcon } from "./icons";
import type { AppSection } from "../types";

interface SidebarProps {
  activeSection: AppSection;
  onSelectSection: (section: AppSection) => void;
}

const STATS_SECTIONS: AppSection[] = ["estadisticas-trenes", "estadisticas-tiempos", "estadisticas-global"];

function navItemClass(active: boolean, sub = false): string {
  let className = "sidebar-nav__item";
  if (sub) className += " sidebar-nav__item--sub";
  if (active) className += " sidebar-nav__item--active";
  return className;
}

export function Sidebar({ activeSection, onSelectSection }: SidebarProps) {
  const [statsOpen, setStatsOpen] = useState(STATS_SECTIONS.includes(activeSection));
  // Menú hamburguesa: el <aside> vive fuera de pantalla por defecto y se
  // desliza como overlay al pulsar este botón, con un fondo oscurecido
  // detrás que también lo cierra al tocarlo (ver index.css) — igual en
  // escritorio que en móvil, no solo bajo el breakpoint de 480px.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!sidebarOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setSidebarOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sidebarOpen]);

  function selectSection(section: AppSection) {
    onSelectSection(section);
    setSidebarOpen(false);
  }

  return (
    <>
      <button
        type="button"
        className="sidebar-toggle icon-btn icon-btn--glass"
        aria-label={sidebarOpen ? "Cerrar menú" : "Abrir menú"}
        aria-expanded={sidebarOpen}
        onClick={() => setSidebarOpen((open) => !open)}
      >
        <MenuIcon />
      </button>

      {sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
      )}

      <aside className={`app-sidebar glass${sidebarOpen ? " app-sidebar--open" : ""}`}>
        <nav className="sidebar-nav" aria-label="Navegación principal">
          <button
            type="button"
            className={navItemClass(activeSection === "seguimiento")}
            aria-current={activeSection === "seguimiento" ? "page" : undefined}
            onClick={() => selectSection("seguimiento")}
          >
            Seguimiento de trenes
          </button>

          <button
            type="button"
            className={navItemClass(activeSection === "horarios")}
            aria-current={activeSection === "horarios" ? "page" : undefined}
            onClick={() => selectSection("horarios")}
          >
            Horarios de trenes AVE
          </button>

          <button
            type="button"
            className="sidebar-nav__group"
            aria-expanded={statsOpen}
            onClick={() => setStatsOpen((open) => !open)}
          >
            <span>Estadísticas</span>
            <ChevronRightIcon
              className={`sidebar-nav__chevron${statsOpen ? " sidebar-nav__chevron--open" : ""}`}
            />
          </button>

          {statsOpen && (
            <div className="sidebar-nav__subgroup">
              <button
                type="button"
                className={navItemClass(activeSection === "estadisticas-trenes", true)}
                aria-current={activeSection === "estadisticas-trenes" ? "page" : undefined}
                onClick={() => selectSection("estadisticas-trenes")}
              >
                Por trenes
              </button>
              <button
                type="button"
                className={navItemClass(activeSection === "estadisticas-tiempos", true)}
                aria-current={activeSection === "estadisticas-tiempos" ? "page" : undefined}
                onClick={() => selectSection("estadisticas-tiempos")}
              >
                Por tiempos
              </button>
              <button
                type="button"
                className={navItemClass(activeSection === "estadisticas-global", true)}
                aria-current={activeSection === "estadisticas-global" ? "page" : undefined}
                onClick={() => selectSection("estadisticas-global")}
              >
                Global
              </button>
            </div>
          )}
        </nav>
      </aside>
    </>
  );
}
