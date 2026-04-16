"use client";

import { Briefcase, ChevronDown, LogOut, Moon, Search, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { useEffect, useRef, useState } from "react";
import { CommandPalette, useCommandPalette } from "@/shared/components/command-palette";
import { ConnectionStatus } from "@/shared/components/connection-status";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTheme } from "@/shared/hooks/use-theme";
import { cn } from "@/shared/lib/cn";
import { Permission } from "@/shared/lib/permissions";
import { FundSelector } from "./fund-selector";

// ─── Nav Structure ─────────────────────────────────────────

interface NavLink {
  label: string;
  href: string;
  permission?: Permission;
}

interface NavSection {
  label: string;
  href?: string;
  children?: NavLink[];
  permission?: Permission;
}

const NAV_SECTIONS: NavSection[] = [
  { label: "Dashboard", href: "" },
  {
    label: "Trading",
    children: [
      { label: "Portfolios", href: "/portfolio", permission: Permission.POSITIONS_READ },
      { label: "Orders", href: "/orders", permission: Permission.ORDERS_READ },
      { label: "FX Hedging", href: "/fx-hedging", permission: Permission.FX_HEDGING_READ },
    ],
  },
  {
    label: "Risk & Analytics",
    children: [
      { label: "Risk", href: "/risk", permission: Permission.RISK_READ },
      { label: "Exposure", href: "/exposure", permission: Permission.EXPOSURE_READ },
      { label: "Attribution", href: "/attribution", permission: Permission.ATTRIBUTION_READ },
      { label: "Alpha", href: "/alpha", permission: Permission.ALPHA_READ },
      { label: "TCA", href: "/tca", permission: Permission.ORDERS_READ },
    ],
  },
  {
    label: "Operations",
    children: [
      { label: "Cash", href: "/cash", permission: Permission.CASH_READ },
      { label: "EOD & NAV", href: "/eod", permission: Permission.RISK_READ },
      { label: "Fees", href: "/fees", permission: Permission.CAPITAL_READ },
      { label: "Corp Actions", href: "/corporate-actions", permission: Permission.POSITIONS_READ },
      { label: "Investors", href: "/investors", permission: Permission.CAPITAL_READ },
    ],
  },
  { label: "Compliance", href: "/compliance", permission: Permission.COMPLIANCE_READ },
  {
    label: "Data",
    children: [
      { label: "Instruments", href: "/instruments", permission: Permission.INSTRUMENTS_READ },
      { label: "Market Data", href: "/market-data", permission: Permission.PRICES_READ },
    ],
  },
];

// ─── TopNav Component ──────────────────────────────────────

export function TopNav() {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const pathname = usePathname();
  const { data: session } = useSession();
  const { theme, toggle } = useTheme();
  const { open, setOpen } = useCommandPalette();

  const userName = session?.user?.name ?? "User";
  const userInitials = userName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <>
      <header
        className="flex h-12 items-center border-b border-[var(--border)] bg-[var(--sidebar)]"
        style={{ backgroundImage: "var(--sidebar-gradient)" }}
      >
        {/* Left: Logo + Fund */}
        <div className="flex items-center gap-3 border-r border-[var(--border)] px-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--primary)]">
            <Briefcase className="h-3.5 w-3.5 text-white" />
          </div>
          <FundSelector />
        </div>

        {/* Center: Navigation */}
        <nav className="flex flex-1 items-center gap-0.5 px-2">
          {NAV_SECTIONS.map((section) => {
            // Check top-level permission
            if (section.permission && !can(section.permission)) return null;

            // Filter children by permission
            const visibleChildren = section.children?.filter(
              (c) => !c.permission || can(c.permission),
            );
            if (section.children && (!visibleChildren || visibleChildren.length === 0)) return null;

            // Direct link (no dropdown)
            if (section.href !== undefined && !section.children) {
              const fullHref = `/${fundSlug}${section.href}`;
              const active =
                section.href === "" ? pathname === `/${fundSlug}` : pathname.startsWith(fullHref);

              return (
                <Link
                  key={section.label}
                  href={fullHref}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    active
                      ? "bg-[var(--sidebar-active)] text-[var(--primary)]"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--sidebar-active)] hover:text-[var(--foreground)]",
                  )}
                >
                  {section.label}
                </Link>
              );
            }

            // Dropdown
            return (
              <NavDropdown
                key={section.label}
                label={section.label}
                items={visibleChildren ?? []}
                fundSlug={fundSlug}
                pathname={pathname}
              />
            );
          })}
        </nav>

        {/* Right: Search, Connection, Theme, User */}
        <div className="flex items-center gap-2 px-4">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="hidden h-7 w-44 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--sidebar-active)] px-2.5 text-xs text-[var(--muted-foreground)] transition-colors hover:border-[var(--primary)] sm:flex"
          >
            <Search className="h-3.5 w-3.5 shrink-0" />
            <span className="flex-1 text-left">Search...</span>
            <kbd className="rounded border border-[var(--border)] px-1 py-0.5 font-mono text-[9px] leading-none">
              &#8984;K
            </kbd>
          </button>

          <ConnectionStatus />

          <button
            type="button"
            onClick={toggle}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--sidebar-active)] hover:text-[var(--foreground)]"
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          </button>

          <UserMenu userName={userName} userInitials={userInitials} />
        </div>
      </header>

      <CommandPalette open={open} onOpenChange={setOpen} />
    </>
  );
}

// ─── NavDropdown ───────────────────────────────────────────

function NavDropdown({
  label,
  items,
  fundSlug,
  pathname,
}: {
  label: string;
  items: NavLink[];
  fundSlug: string;
  pathname: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const isActive = items.some((item) => pathname.startsWith(`/${fundSlug}${item.href}`));

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
          isActive
            ? "bg-[var(--sidebar-active)] text-[var(--primary)]"
            : "text-[var(--muted-foreground)] hover:bg-[var(--sidebar-active)] hover:text-[var(--foreground)]",
        )}
      >
        {label}
        <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[180px] rounded-md border border-[var(--border)] bg-[var(--background-raised)] py-1 shadow-xl">
          {items.map((item) => {
            const href = `/${fundSlug}${item.href}`;
            const active = pathname.startsWith(href);
            return (
              <Link
                key={item.href}
                href={href}
                onClick={() => setOpen(false)}
                className={cn(
                  "block px-3 py-1.5 text-xs transition-colors",
                  active
                    ? "bg-[var(--primary-muted)] font-medium text-[var(--primary)]"
                    : "text-[var(--foreground)] hover:bg-[var(--muted)]",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── UserMenu ──────────────────────────────────────────────

function UserMenu({ userName, userInitials }: { userName: string; userInitials: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { fundSlug } = useFundContext();

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleLogout = async () => {
    const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER ?? "";
    const clientId = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "";
    const logoutUrl = `${issuer}/protocol/openid-connect/logout`;
    const redirectUri = encodeURIComponent(`${window.location.origin}/login`);
    await signOut({ redirect: false });
    window.location.href = `${logoutUrl}?post_logout_redirect_uri=${redirectUri}&client_id=${clientId}`;
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--primary)] text-[10px] font-bold text-white transition-opacity hover:opacity-80"
        title={userName}
      >
        {userInitials}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[180px] rounded-md border border-[var(--border)] bg-[var(--background-raised)] py-1 shadow-xl">
          <div className="border-b border-[var(--border)] px-3 py-2">
            <p className="text-xs font-medium text-[var(--foreground)]">{userName}</p>
            <p className="text-[10px] text-[var(--muted-foreground)]">Manager</p>
          </div>
          <Link
            href={`/${fundSlug}/settings`}
            onClick={() => setOpen(false)}
            className="block px-3 py-1.5 text-xs text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
          >
            Settings
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-[var(--destructive)] transition-colors hover:bg-[var(--muted)]"
          >
            <LogOut className="h-3 w-3" />
            Logout
          </button>
        </div>
      )}
    </div>
  );
}
