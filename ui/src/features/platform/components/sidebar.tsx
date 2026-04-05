"use client";

import {
  AlertTriangle,
  BarChart3,
  Briefcase,
  ChevronDown,
  ClipboardList,
  LayoutDashboard,
  Lightbulb,
  PieChart,
  Search,
  Settings,
  ShieldCheck,
  TrendingUp,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { cn } from "@/shared/lib/cn";
import { NAV_ITEMS, type NavItem } from "@/shared/lib/navigation";
import { LogoutButton } from "./logout-button";

const ICONS = {
  LayoutDashboard,
  Briefcase,
  Search,
  TrendingUp,
  ShieldCheck,
  ClipboardList,
  BarChart3,
  AlertTriangle,
  Wallet,
  PieChart,
  Lightbulb,
  Settings,
} as const;

/* Group nav items by category for the collapsible sections */
interface NavGroup {
  label: string;
  items: NavItem[];
  defaultOpen?: boolean;
}

function groupNavItems(items: NavItem[]): NavGroup[] {
  const dashboard = items.filter((i) => i.href === "");
  const portfolio = items.filter((i) => ["/portfolio", "/orders", "/exposure"].includes(i.href));
  const riskCompliance = items.filter((i) => ["/compliance", "/risk"].includes(i.href));
  const operations = items.filter((i) => ["/cash", "/attribution", "/alpha"].includes(i.href));
  const reference = items.filter((i) => ["/instruments", "/market-data"].includes(i.href));
  const settings = items.filter((i) => i.href === "/settings");

  return [
    { label: "", items: dashboard, defaultOpen: true },
    { label: "Portfolio", items: portfolio, defaultOpen: true },
    { label: "Risk & Compliance", items: riskCompliance, defaultOpen: true },
    { label: "Operations", items: operations, defaultOpen: true },
    { label: "Reference Data", items: reference, defaultOpen: true },
    { label: "Settings", items: settings, defaultOpen: true },
  ].filter((g) => g.items.length > 0);
}

export function Sidebar() {
  const { can } = usePermission();
  const { fundSlug } = useFundContext();
  const pathname = usePathname();
  const { data: session } = useSession();

  const visibleItems = NAV_ITEMS.filter((item) => !item.permission || can(item.permission));
  const groups = groupNavItems(visibleItems);

  const userName = session?.user?.name ?? "User";
  const userInitials = userName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <aside
      className="flex h-full w-[var(--sidebar-width)] flex-col border-r border-[var(--border)] bg-[var(--sidebar)]"
      style={{ backgroundImage: "var(--sidebar-gradient)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]">
          <Briefcase className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold tracking-wide text-[var(--foreground-bright)]">
          MINI-HEDGE
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
        {groups.map((group) => (
          <NavSection
            key={group.label || "top"}
            group={group}
            fundSlug={fundSlug}
            pathname={pathname}
          />
        ))}
      </nav>

      {/* User profile at bottom */}
      <div className="border-t border-[var(--border)] px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--warning)] text-xs font-bold text-black">
            {userInitials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-[var(--foreground-bright)]">
              {userName}
            </p>
            <p className="truncate text-xs text-[var(--muted-foreground)]">Manager</p>
          </div>
        </div>
        <div className="mt-3">
          <LogoutButton />
        </div>
      </div>
    </aside>
  );
}

function NavSection({
  group,
  fundSlug,
  pathname,
}: {
  group: NavGroup;
  fundSlug: string;
  pathname: string;
}) {
  const [open, setOpen] = useState(group.defaultOpen ?? true);

  // Top-level items (Dashboard) — no collapsible header
  if (!group.label) {
    return (
      <div className="mb-2">
        {group.items.map((item) => (
          <SidebarLink
            key={item.href}
            item={item}
            fundSlug={fundSlug}
            active={isActive(pathname, fundSlug, item.href)}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        {group.label}
        <ChevronDown
          className={cn("h-3 w-3 transition-transform", open ? "rotate-0" : "-rotate-90")}
        />
      </button>
      {open && (
        <div className="space-y-0.5">
          {group.items.map((item) => (
            <SidebarLink
              key={item.href}
              item={item}
              fundSlug={fundSlug}
              active={isActive(pathname, fundSlug, item.href)}
            />
          ))}
        </div>
      )}
    </div>
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
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
        active
          ? "bg-[var(--sidebar-active)] font-medium text-[var(--primary)]"
          : "text-[var(--muted-foreground)] hover:bg-[var(--sidebar-active)] hover:text-[var(--foreground)]",
      )}
    >
      <Icon className={cn("h-4 w-4", active && "text-[var(--primary)]")} />
      {item.label}
    </Link>
  );
}

function isActive(pathname: string, fundSlug: string, href: string): boolean {
  const fullPath = `/${fundSlug}${href}`;
  if (href === "") return pathname === `/${fundSlug}`;
  return pathname.startsWith(fullPath);
}
