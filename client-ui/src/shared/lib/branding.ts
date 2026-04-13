export interface BrandingConfig {
  /** Display name shown in sidebar and page title */
  portalName: string;
  /** Subtitle shown under portal name */
  portalSubtitle: string;
  /** Primary brand color (hex) */
  primaryColor: string;
  /** Primary color for text on primary backgrounds */
  primaryForeground: string;
  /** Accent/highlight color */
  accentColor: string;
  /** Sidebar background color */
  sidebarColor: string;
  /** Optional logo URL (displayed in sidebar header) */
  logoUrl?: string;
  /** Favicon URL */
  faviconUrl?: string;
}

/** Default branding — used when no customer override is set */
export const DEFAULT_BRANDING: BrandingConfig = {
  portalName: "Investor Portal",
  portalSubtitle: "Secure Access",
  primaryColor: "#1e3a5f",
  primaryForeground: "#ffffff",
  accentColor: "#f0f4ff",
  sidebarColor: "#f8fafc",
};

/**
 * Resolve branding config.
 *
 * In production, this would fetch from the backend based on the customer's
 * subdomain or auth context. For now, reads from environment variables
 * with fallback to defaults.
 */
export function resolveBranding(): BrandingConfig {
  return {
    portalName:
      process.env.NEXT_PUBLIC_PORTAL_NAME ?? DEFAULT_BRANDING.portalName,
    portalSubtitle:
      process.env.NEXT_PUBLIC_PORTAL_SUBTITLE ?? DEFAULT_BRANDING.portalSubtitle,
    primaryColor:
      process.env.NEXT_PUBLIC_PRIMARY_COLOR ?? DEFAULT_BRANDING.primaryColor,
    primaryForeground:
      process.env.NEXT_PUBLIC_PRIMARY_FOREGROUND ??
      DEFAULT_BRANDING.primaryForeground,
    accentColor:
      process.env.NEXT_PUBLIC_ACCENT_COLOR ?? DEFAULT_BRANDING.accentColor,
    sidebarColor:
      process.env.NEXT_PUBLIC_SIDEBAR_COLOR ?? DEFAULT_BRANDING.sidebarColor,
    logoUrl: process.env.NEXT_PUBLIC_LOGO_URL,
    faviconUrl: process.env.NEXT_PUBLIC_FAVICON_URL,
  };
}

/** Convert hex to rgba for muted variants */
export function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
