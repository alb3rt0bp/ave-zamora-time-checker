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
  // Menú hamburguesa clásico en móvil: el <aside> vive fuera de pantalla por
  // defecto (ver index.css, breakpoint 480px) y se desliza como overlay al
  // pulsar este botón. En escritorio mobileOpen no tiene efecto visual (el
  // botón y el fondo oscurecido solo se muestran bajo ese breakpoint).
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!mobileOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMobileOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen]);

  function selectSection(section: AppSection) {
    onSelectSection(section);
    setMobileOpen(false);
  }

  return (
    <>
      <button
        type="button"
        className="sidebar-toggle icon-btn icon-btn--glass"
        aria-label={mobileOpen ? "Cerrar menú" : "Abrir menú"}
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((open) => !open)}
      >
        <MenuIcon />
      </button>

      {mobileOpen && (
        <div className="sidebar-backdrop" onClick={() => setMobileOpen(false)} aria-hidden="true" />
      )}

      <aside className={`app-sidebar glass${mobileOpen ? " app-sidebar--open" : ""}`}>
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
