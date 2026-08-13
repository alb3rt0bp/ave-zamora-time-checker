import { describe, expect, it } from "vitest";
import { computeZoomForScale } from "./mapScale";

describe("computeZoomForScale", () => {
  it("computes a zoom around 9.8 for the Zamora area at the default 1cm:5km scale", () => {
    const zoom = computeZoomForScale(41.5);

    expect(zoom).toBeGreaterThan(9.5);
    expect(zoom).toBeLessThan(10.1);
  });

  it("requires a higher zoom for a tighter scale (fewer km per cm)", () => {
    const wideScale = computeZoomForScale(41.5, 10);
    const tightScale = computeZoomForScale(41.5, 5);

    expect(tightScale).toBeGreaterThan(wideScale);
  });

  it("requires a higher zoom closer to the equator, for the same scale", () => {
    const nearEquator = computeZoomForScale(5);
    const zamoraLatitude = computeZoomForScale(41.5);

    // A latitud alta, la proyección Mercator ya "acerca" el terreno por
    // píxel (factor cos(lat)), así que hace falta menos zoom para la misma
    // escala real que cerca del ecuador.
    expect(nearEquator).toBeGreaterThan(zamoraLatitude);
  });
});
