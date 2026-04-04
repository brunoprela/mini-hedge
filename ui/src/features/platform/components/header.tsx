"use client";

import { Moon, Search, Sun } from "lucide-react";
import { ConnectionStatus } from "@/shared/components/connection-status";
import { useTheme } from "@/shared/hooks/use-theme";
import { FundSelector } from "./fund-selector";

export function Header() {
  const { theme, toggle } = useTheme();

  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--background-raised)] px-6">
      <FundSelector />

      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]" />
          <input
            type="text"
            placeholder="Search here..."
            className="h-8 w-56 rounded-lg border border-[var(--input-border)] bg-[var(--input)] pl-9 pr-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
          />
        </div>

        <ConnectionStatus />

        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggle}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}
