"use client";

import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";

interface CollapsibleSectionProps {
  /** Section title displayed in the header */
  title: string;
  /** Whether the section starts expanded (default: true) */
  defaultOpen?: boolean;
  /** Main content */
  children: ReactNode;
}

/**
 * Collapsible accordion section with smooth CSS grid animation.
 * Uses the grid-template-rows trick for height transitions.
 */
export function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-md border border-[var(--border)]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between bg-[var(--primary-muted)] px-3 py-2 text-left"
      >
        <span className="text-xs font-semibold text-[var(--foreground)]">{title}</span>
        <ChevronDown
          className={`h-4 w-4 text-[var(--muted-foreground)] transition-transform duration-200 ${open ? "rotate-0" : "-rotate-90"}`}
        />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-200 ease-out"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="bg-[var(--card)] p-3">{children}</div>
        </div>
      </div>
    </div>
  );
}
