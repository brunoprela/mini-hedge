import type { Metadata } from "next";
import { Providers } from "@/shared/lib/providers";
import { BrandingProvider } from "@/shared/lib/branding-provider";
import { BrandingStyle } from "@/shared/components/branding-style";
import { resolveBranding } from "@/shared/lib/branding";
import "./globals.css";

const branding = resolveBranding();

export const metadata: Metadata = {
  title: branding.portalName,
  description: branding.portalSubtitle,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <BrandingProvider config={branding}>
          <BrandingStyle />
          <Providers>{children}</Providers>
        </BrandingProvider>
      </body>
    </html>
  );
}
