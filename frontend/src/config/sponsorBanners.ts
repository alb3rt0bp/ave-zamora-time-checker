export interface SponsorCreative {
  imageUrl: string;
  linkUrl: string;
  // Píxel 1x1 con el que la red de afiliación cuenta impresiones.
  pixelUrl?: string;
}

export interface SponsorBannerConfig {
  name: string;
  creative: SponsorCreative;
  // Variante para pantallas estrechas; sin ella se usa creative también ahí.
  mobileCreative?: SponsorCreative;
}

// Patrocinio directo (banner de imagen + enlace de un patrocinador), sin
// red de anuncios ni cookies de terceros. null muestra un hueco reservado
// (ver SponsorBanner.tsx) en vez del banner.
// Omio vía impact.com (Brand Creatives > Images > Asset Code, versión HTML):
// las imágenes se sirven tal cual desde Omio/impact.com, sin redimensionar
// ni alojar aquí. Cada creatividad tiene su propio enlace y píxel.
const OMIO: SponsorBannerConfig = {
  name: "Omio",
  creative: {
    imageUrl: "https://storage.googleapis.com/omio-performance/Banners/ES/970x90_.png",
    linkUrl: "https://omio.sjv.io/c/7864340/568966/7385",
    pixelUrl: "https://omio.sjv.io/i/7864340/568966/7385",
  },
  mobileCreative: {
    imageUrl: "https://a.impactradius-go.com/display-ad/7385-581371",
    linkUrl: "https://omio.sjv.io/c/7864340/581371/7385",
    pixelUrl: "https://omio.sjv.io/i/7864340/581371/7385",
  },
};

export const SPONSOR_TOP: SponsorBannerConfig | null = OMIO;
export const SPONSOR_BOTTOM: SponsorBannerConfig | null = OMIO;
