"use client";

import { BarChart3, Bell, Building2, FileText, Key, User, Wallet, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { useBranding } from "@/shared/lib/branding-provider";
import { useMobileNav } from "@/shared/lib/use-mobile-nav";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: BarChart3 },
  { href: "/funds", label: "My Funds", icon: Building2 },
  { href: "/activity", label: "Capital Activity", icon: Wallet },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/profile", label: "Profile", icon: User },
];

export function Sidebar() {
  const pathname = usePathname();
  const branding = useBranding();
  const { isOpen, close } = useMobileNav();

  return (
    <>
      {/* Mobile backdrop */}
      <button
        type="button"
        aria-label="Close navigation"
        onClick={close}
        className={`lg:hidden fixed inset-0 z-30 bg-black/40 transition-opacity duration-200 ${
          isOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        className={`fixed left-0 top-0 z-40 h-full w-[var(--sidebar-width)] border-r border-[var(--border)] bg-[var(--sidebar)] flex flex-col transition-transform duration-200 ease-out lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Primary navigation"
      >
        <div className="p-5 border-b border-[var(--border)] flex items-start justify-between gap-2">
          <div className="min-w-0">
            {branding.logoUrl && (
              <img src={branding.logoUrl} alt={branding.portalName} className="h-8 mb-2" />
            )}
            <h1 className="text-lg font-semibold text-[var(--primary)] truncate">
              {branding.portalName}
            </h1>
            <p className="text-xs text-[var(--muted-foreground)] truncate">
              {branding.portalSubtitle}
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            aria-label="Close navigation"
            className="lg:hidden -mr-2 -mt-1 inline-flex h-11 w-11 items-center justify-center rounded-md text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 rounded-md px-3 py-2.5 text-sm min-h-11 ${
                  active
                    ? "bg-[var(--accent)] text-[var(--accent-foreground)] font-medium"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-[var(--border)]">
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-sm min-h-11 text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          >
            <Key size={16} />
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
