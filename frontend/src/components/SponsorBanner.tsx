import type { SponsorBannerConfig } from "../config/sponsorBanners";
import { useMediaQuery } from "../hooks/useMediaQuery";

// Mismo corte móvil/escritorio que el resto de index.css (min-width: 640px).
const MOBILE_QUERY = "(max-width: 639px)";

interface SponsorBannerProps {
  slot: "top" | "bottom";
  sponsor: SponsorBannerConfig | null;
  hideOnMobile?: boolean;
}

// Banner de patrocinio directo (imagen + enlace), del ancho del contenido
// de la página. Se usa por duplicado en cada pantalla (arriba y abajo del
// contenido principal), salvo en las ventanas modales. Sin patrocinador
// configurado todavía (sponsorBanners.ts), reserva el hueco con un
// placeholder visual en vez de mostrar un enlace roto.
// La creatividad móvil se elige en JS y no con <picture>/CSS para que solo
// se cargue el píxel de impresiones de la que el usuario ve de verdad.
export function SponsorBanner({ slot, sponsor, hideOnMobile = false }: SponsorBannerProps) {
  const isMobile = useMediaQuery(MOBILE_QUERY);

  if (hideOnMobile && isMobile) return null;

  if (!sponsor) {
    return (
      <div
        className={`sponsor-banner sponsor-banner--${slot} sponsor-banner--placeholder table-card glass`}
        aria-label="Patrocinador (hueco reservado)"
      >
        <p className="sponsor-banner__placeholder-text">Espacio reservado para patrocinador</p>
      </div>
    );
  }

  const creative = (isMobile && sponsor.mobileCreative) || sponsor.creative;

  return (
    <>
      <a
        href={creative.linkUrl}
        target="_blank"
        rel="noopener noreferrer sponsored"
        className={`sponsor-banner sponsor-banner--${slot} table-card glass`}
        aria-label={`Patrocinador: ${sponsor.name}`}
      >
        <img src={creative.imageUrl} alt={sponsor.name} className="sponsor-banner__image" />
      </a>
      {creative.pixelUrl && (
        <img src={creative.pixelUrl} alt="" aria-hidden="true" width={0} height={0} className="sponsor-banner__pixel" />
      )}
    </>
  );
}
