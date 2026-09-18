import type { SVGProps } from "react";

// Conjunto mínimo de iconos dibujados a mano (trazo simple, geométrico):
// solo 3 glifos funcionales, no decorativos, así que no justifica añadir una
// librería de iconos completa como dependencia de producción.
function baseProps(props: SVGProps<SVGSVGElement>): SVGProps<SVGSVGElement> {
  return {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
    focusable: false,
    ...props,
  };
}

export function ChevronLeftIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps(props)}>
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

export function ChevronRightIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps(props)}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function MapPinIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps(props)}>
      <path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11Z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

export function MenuIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps(props)}>
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="17" x2="20" y2="17" />
    </svg>
  );
}

// Botón de volteo (mapa en vivo <-> detalle estadístico de un mismo tren):
// dos flechas opuestas en vez de un símbolo de "recargar", para no
// confundirse con el ↻ de refresco de la barra de herramientas.
export function FlipIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps(props)}>
      <polyline points="17 4 21 8 17 12" />
      <line x1="21" y1="8" x2="3" y2="8" />
      <polyline points="7 12 3 16 7 20" />
      <line x1="3" y1="16" x2="21" y2="16" />
    </svg>
  );
}
