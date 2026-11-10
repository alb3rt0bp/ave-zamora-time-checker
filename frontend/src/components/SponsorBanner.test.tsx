import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SponsorBannerConfig } from "../config/sponsorBanners";
import { SponsorBanner } from "./SponsorBanner";

const DESKTOP = {
  imageUrl: "https://example.com/omio-970x90.png",
  linkUrl: "https://example.com/omio-desktop",
  pixelUrl: "https://example.com/omio-desktop-pixel",
};

const MOBILE = {
  imageUrl: "https://example.com/omio-320x100.png",
  linkUrl: "https://example.com/omio-mobile",
  pixelUrl: "https://example.com/omio-mobile-pixel",
};

const SPONSOR: SponsorBannerConfig = { name: "Omio", creative: DESKTOP, mobileCreative: MOBILE };

function emulateViewport(isMobile: boolean) {
  vi.spyOn(window, "matchMedia").mockImplementation(
    (query: string) =>
      ({
        matches: isMobile,
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

describe("SponsorBanner", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows a reserved placeholder in the top slot when no sponsor is configured", () => {
    render(<SponsorBanner slot="top" sponsor={null} />);

    expect(screen.getByText("Espacio reservado para patrocinador")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows a reserved placeholder in the bottom slot when no sponsor is configured", () => {
    render(<SponsorBanner slot="bottom" sponsor={null} />);

    expect(screen.getByText("Espacio reservado para patrocinador")).toBeInTheDocument();
  });

  it("renders the desktop creative linking out on wide screens", () => {
    emulateViewport(false);
    render(<SponsorBanner slot="top" sponsor={SPONSOR} />);

    const link = screen.getByRole("link", { name: /omio/i });
    expect(link).toHaveAttribute("href", DESKTOP.linkUrl);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("sponsored"));
    expect(screen.getByRole("img", { name: "Omio" })).toHaveAttribute("src", DESKTOP.imageUrl);
  });

  it("renders the mobile creative on narrow screens", () => {
    emulateViewport(true);
    render(<SponsorBanner slot="bottom" sponsor={SPONSOR} />);

    expect(screen.getByRole("link", { name: /omio/i })).toHaveAttribute("href", MOBILE.linkUrl);
    expect(screen.getByRole("img", { name: "Omio" })).toHaveAttribute("src", MOBILE.imageUrl);
  });

  it("falls back to the desktop creative on narrow screens when there is no mobile one", () => {
    emulateViewport(true);
    render(<SponsorBanner slot="top" sponsor={{ name: "Omio", creative: DESKTOP }} />);

    expect(screen.getByRole("img", { name: "Omio" })).toHaveAttribute("src", DESKTOP.imageUrl);
  });

  it("loads only the impression pixel of the creative being shown, outside the link", () => {
    emulateViewport(true);
    const { container } = render(<SponsorBanner slot="top" sponsor={SPONSOR} />);

    const pixel = container.querySelector(`img[src="${MOBILE.pixelUrl}"]`);
    expect(pixel).not.toBeNull();
    expect(pixel).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("link").contains(pixel)).toBe(false);
    expect(container.querySelector(`img[src="${DESKTOP.pixelUrl}"]`)).toBeNull();
  });

  it("renders nothing on narrow screens when hideOnMobile is set", () => {
    emulateViewport(true);
    const { container } = render(<SponsorBanner slot="top" sponsor={SPONSOR} hideOnMobile />);

    expect(container).toBeEmptyDOMElement();
  });

  it("still renders on wide screens when hideOnMobile is set", () => {
    emulateViewport(false);
    render(<SponsorBanner slot="top" sponsor={SPONSOR} hideOnMobile />);

    expect(screen.getByRole("img", { name: "Omio" })).toHaveAttribute("src", DESKTOP.imageUrl);
  });

  it("renders no impression pixel when the creative has none", () => {
    const { container } = render(
      <SponsorBanner slot="top" sponsor={{ name: "Omio", creative: { ...DESKTOP, pixelUrl: undefined } }} />,
    );

    expect(container.querySelectorAll("img")).toHaveLength(1);
  });
});
