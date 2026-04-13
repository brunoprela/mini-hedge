"use client";

import { createContext, useContext, type ReactNode } from "react";
import { type BrandingConfig, DEFAULT_BRANDING } from "./branding";

const BrandingContext = createContext<BrandingConfig>(DEFAULT_BRANDING);

export function useBranding() {
  return useContext(BrandingContext);
}

export function BrandingProvider({
  config,
  children,
}: {
  config: BrandingConfig;
  children: ReactNode;
}) {
  return (
    <BrandingContext.Provider value={config}>
      {children}
    </BrandingContext.Provider>
  );
}
