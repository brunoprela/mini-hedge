"use client";

import { Menu } from "lucide-react";
import { useBranding } from "@/shared/lib/branding-provider";
import { useMobileNav } from "@/shared/lib/use-mobile-nav";

export function MobileHeader() {
  const branding = useBranding();
  const { toggle, isOpen } = useMobileNav();

  return (
    <header className="lg:hidden sticky top-0 z-20 flex items-center gap-3 border-b border-[var(--border)] bg-[var(--background)] px-4 py-2">
      <button
        type="button"
        onClick={toggle}
        aria-label="Open navigation"
        aria-expanded={isOpen}
        className="inline-flex h-11 w-11 items-center justify-center rounded-md text-[var(--foreground)] hover:bg-[var(--muted)]"
      >
        <Menu size={22} />
      </button>
      <div className="min-w-0 flex items-center gap-2">
        {branding.logoUrl && (
          <img src={branding.logoUrl} alt={branding.portalName} className="h-6" />
        )}
        <span className="text-base font-semibold text-[var(--primary)] truncate">
          {branding.portalName}
        </span>
      </div>
    </header>
  );
}
