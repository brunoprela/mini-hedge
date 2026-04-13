"use client";

import { useBranding } from "@/shared/lib/branding-provider";
import { hexToRgba } from "@/shared/lib/branding";

/**
 * Injects CSS variable overrides based on the branding config.
 * Placed in the layout so all pages inherit the overrides.
 */
export function BrandingStyle() {
  const branding = useBranding();

  const overrides = {
    "--primary": branding.primaryColor,
    "--primary-foreground": branding.primaryForeground,
    "--primary-muted": hexToRgba(branding.primaryColor, 0.08),
    "--accent": branding.accentColor,
    "--accent-foreground": branding.primaryColor,
    "--sidebar": branding.sidebarColor,
    "--ring": hexToRgba(branding.primaryColor, 0.25),
  };

  const css = `:root { ${Object.entries(overrides)
    .map(([k, v]) => `${k}: ${v}`)
    .join("; ")} }`;

  return <style dangerouslySetInnerHTML={{ __html: css }} />;
}
