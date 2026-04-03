"use client";

import { ConnectionStatus } from "@/shared/components/connection-status";
import { FundSelector } from "./fund-selector";
import { LogoutButton } from "./logout-button";

export function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] px-6">
      <FundSelector />
      <div className="flex items-center gap-4">
        <ConnectionStatus />
        <LogoutButton />
      </div>
    </header>
  );
}
