"use client";

/**
 * Tabs — controlled tab list + panel renderer.
 *
 * Keeps state in the parent for URL-sync friendliness. For uncontrolled behaviour
 * pair with `useState` at the call site.
 */

import type { ReactNode } from "react";

export interface TabItem {
  id: string;
  label: ReactNode;
  /** Optional trailing badge/count rendered after the label. */
  badge?: ReactNode;
  disabled?: boolean;
}

interface TabsProps {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  /** Variant — `underline` (default) or `pill`. */
  variant?: "underline" | "pill";
  className?: string;
}

export function Tabs({ items, activeId, onChange, variant = "underline", className = "" }: TabsProps) {
  if (variant === "pill") {
    return (
      <div role="tablist" className={`inline-flex gap-1 rounded-lg bg-[var(--muted)] p-1 ${className}`}>
        {items.map((item) => {
          const active = item.id === activeId;
          return (
            <button
              key={item.id}
              role="tab"
              type="button"
              aria-selected={active}
              disabled={item.disabled}
              onClick={() => onChange(item.id)}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                active
                  ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {item.label}
              {item.badge && (
                <span className="rounded-full bg-[var(--muted-foreground)]/20 px-1.5 text-[10px]">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      role="tablist"
      className={`flex items-center gap-4 border-b border-[var(--border)] ${className}`}
    >
      {items.map((item) => {
        const active = item.id === activeId;
        return (
          <button
            key={item.id}
            role="tab"
            type="button"
            aria-selected={active}
            disabled={item.disabled}
            onClick={() => onChange(item.id)}
            className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-1 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
              active
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {item.label}
            {item.badge && (
              <span className="rounded-full bg-[var(--muted)] px-1.5 text-[10px] text-[var(--muted-foreground)]">
                {item.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Conditional panel renderer — shows children only when `id === activeId`. */
export function TabPanel({
  id,
  activeId,
  children,
}: {
  id: string;
  activeId: string;
  children: ReactNode;
}) {
  if (id !== activeId) return null;
  return (
    <div role="tabpanel" id={`tabpanel-${id}`}>
      {children}
    </div>
  );
}
