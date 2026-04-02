"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  Search,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/shared/lib/cn";
import { NAV_ITEMS, type NavItem } from "@/shared/lib/navigation";
import { usePermission } from "@/shared/hooks/use-permission";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const ICONS = {
  LayoutDashboard,
  Briefcase,
  Search,
  TrendingUp,
} as const;

export function Sidebar() {
  const { can } = usePermission();
  const { fundSlug } = useFundContext();
  const pathname = usePathname();

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.permission || can(item.permission)
  );

  return (
    <aside className="flex h-full w-[var(--sidebar-width)] flex-col border-r border-[var(--border)] bg-[var(--muted)]">
      <div className="px-4 py-5">
        <h2 className="text-sm font-semibold">Mini Hedge</h2>
      </div>
      <nav className="flex-1 space-y-1 px-2">
        {visibleItems.map((item) => (
          <SidebarLink
            key={item.href}
            item={item}
            fundSlug={fundSlug}
            active={isActive(pathname, fundSlug, item.href)}
          />
        ))}
      </nav>
    </aside>
  );
}

function SidebarLink({
  item,
  fundSlug,
  active,
}: {
  item: NavItem;
  fundSlug: string;
  active: boolean;
}) {
  const Icon = ICONS[item.icon];
  const href = `/${fundSlug}${item.href}`;

  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-[var(--background)] font-medium"
          : "text-[var(--muted-foreground)] hover:bg-[var(--background)] hover:text-[var(--foreground)]"
      )}
    >
      <Icon className="h-4 w-4" />
      {item.label}
    </Link>
  );
}

function isActive(pathname: string, fundSlug: string, href: string): boolean {
  const fullPath = `/${fundSlug}${href}`;
  if (href === "") return pathname === `/${fundSlug}`;
  return pathname.startsWith(fullPath);
}
