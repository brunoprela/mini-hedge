"use client";

import { BarChart3, Building2, Key, ScrollText, Shield, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: BarChart3 },
  { href: "/users", label: "Users", icon: Users },
  { href: "/funds", label: "Funds", icon: Building2 },
  { href: "/operators", label: "Operators", icon: Shield },
  { href: "/audit", label: "Audit Log", icon: ScrollText },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-[var(--sidebar-width)] border-r border-[var(--border)] bg-white flex flex-col">
      <div className="p-4 border-b border-[var(--border)]">
        <h1 className="text-lg font-semibold text-[var(--primary)]">Ops Console</h1>
        <p className="text-xs text-[var(--muted-foreground)]">Platform Administration</p>
      </div>

      <nav className="flex-1 p-2 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
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

      <div className="p-2 border-t border-[var(--border)]">
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
