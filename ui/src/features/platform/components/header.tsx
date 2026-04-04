"use client";

import { Moon, Search, Sun } from "lucide-react";
import { CommandPalette, useCommandPalette } from "@/shared/components/command-palette";
import { ConnectionStatus } from "@/shared/components/connection-status";
import { useTheme } from "@/shared/hooks/use-theme";
import { FundSelector } from "./fund-selector";

export function Header() {
  const { theme, toggle } = useTheme();
  const { open, setOpen } = useCommandPalette();

  return (
    <>
      <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--background-raised)] px-6">
        <FundSelector />

        <div className="flex items-center gap-3">
          {/* Search trigger */}
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="relative hidden h-8 w-56 items-center gap-2 rounded-lg border border-[var(--input-border)] bg-[var(--input)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:border-[var(--primary)] sm:flex"
          >
            <Search className="h-4 w-4 shrink-0" />
            <span className="flex-1 text-left">Search...</span>
            <kbd className="pointer-events-none rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px] leading-none">
              &#8984;K
            </kbd>
          </button>

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

      <CommandPalette open={open} onOpenChange={setOpen} />
    </>
  );
}
