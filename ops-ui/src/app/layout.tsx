import type { Metadata } from "next";
import { Providers } from "@/shared/lib/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mini Hedge Ops Console",
  description: "Platform administration dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
