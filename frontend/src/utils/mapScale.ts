// Resolución (metros/píxel) de los tiles slippy-map estándar (256px,
// proyección Web Mercator): a mayor latitud, cada píxel cubre menos terreno,
// de ahí el término cos(latitud). Mismo modelo que usan Leaflet/OSM/Bing.
const EARTH_CIRCUMFERENCE_M = 40075016.686;
const TILE_SIZE_PX = 256;

// 1 cm en pantalla ≈ 37.795 CSS px, asumiendo los 96 CSS px/pulgada estándar
// que usan los navegadores (y de los que parte el propio Leaflet para sus
// niveles de zoom), independientemente de la densidad de píxeles real del
// dispositivo.
const CSS_PX_PER_CM = 96 / 2.54;

/**
 * Nivel de zoom (fraccional) de Leaflet al que 1 cm en pantalla representa
 * `targetKmPerCm` km reales, en la latitud dada.
 */
export function computeZoomForScale(latitudeDeg: number, targetKmPerCm = 5): number {
  const metersPerPixelTarget = (targetKmPerCm * 1000) / CSS_PX_PER_CM;
  const latRad = (latitudeDeg * Math.PI) / 180;
  const metersPerPixelAtZoom0 = (EARTH_CIRCUMFERENCE_M * Math.cos(latRad)) / TILE_SIZE_PX;
  return Math.log2(metersPerPixelAtZoom0 / metersPerPixelTarget);
}
