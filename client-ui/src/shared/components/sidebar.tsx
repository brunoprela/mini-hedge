"use client";

import { BarChart3, Bell, Building2, FileText, Key, User, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { useBranding } from "@/shared/lib/branding-provider";

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

  return (
    <aside className="fixed left-0 top-0 h-full w-[var(--sidebar-width)] border-r border-[var(--border)] bg-[var(--sidebar)] flex flex-col">
      <div className="p-5 border-b border-[var(--border)]">
        {branding.logoUrl && (
          <img src={branding.logoUrl} alt={branding.portalName} className="h-8 mb-2" />
        )}
        <h1 className="text-lg font-semibold text-[var(--primary)]">{branding.portalName}</h1>
        <p className="text-xs text-[var(--muted-foreground)]">{branding.portalSubtitle}</p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm ${
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
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
        >
          <Key size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
