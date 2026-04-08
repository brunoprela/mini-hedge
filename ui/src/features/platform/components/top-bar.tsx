"use client";

import { Moon, Search, Sun } from "lucide-react";
import { useSession } from "next-auth/react";
import { CommandPalette, useCommandPalette } from "@/shared/components/command-palette";
import { ConnectionStatus } from "@/shared/components/connection-status";
import { useTheme } from "@/shared/hooks/use-theme";
import { FundSelector } from "./fund-selector";
import { TopBarUserMenu } from "./top-bar-user-menu";

/**
 * Slim top bar — fund selector, search, connection status, theme toggle, user menu.
 * Navigation lives in the sidebar; this bar is just utilities.
 */
export function TopBar() {
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
        className="flex h-10 items-center border-b border-[var(--border)] bg-[var(--sidebar)]"
        style={{ backgroundImage: "var(--sidebar-gradient)" }}
      >
        {/* Fund selector */}
        <div className="flex items-center px-4">
          <FundSelector />
        </div>

        <div className="flex-1" />

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

          <TopBarUserMenu userName={userName} userInitials={userInitials} />
        </div>
      </header>

      <CommandPalette open={open} onOpenChange={setOpen} />
    </>
  );
}
