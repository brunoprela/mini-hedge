"use client";

/**
 * SectionPanel — titled content block with optional toolbar ribbon and summary strip.
 *
 * Bedrock source: tailwind-templates/application-ui-v4/react/lists/grid-lists/02-with-toolbar.jsx
 * (adapted from the `ui/shared/components/section-panel.tsx` in-repo version).
 */

import type { ReactNode } from "react";

interface SectionPanelProps {
  /** Panel title displayed in the toolbar ribbon. */
  title?: ReactNode;
  /** Tab buttons or controls rendered in the toolbar. */
  tabs?: ReactNode;
  /** Right-side controls (search, export, etc.) rendered in the toolbar. */
  actions?: ReactNode;
  /** Optional inline summary strip below the toolbar. */
  summary?: { label: string; value: string; color?: string }[];
  /** Main content. */
  children: ReactNode;
  className?: string;
}

export function SectionPanel({
  title,
  tabs,
  actions,
  summary,
  children,
  className = "",
}: SectionPanelProps) {
  const hasToolbar = title || tabs || actions;

  return (
    <div className={`overflow-hidden rounded-md border border-[var(--border)] ${className}`}>
      {hasToolbar && (
        <div className="flex items-center justify-between gap-3 bg-[var(--primary-muted)] px-3 py-1.5">
          <div className="flex items-center gap-3">
            {title && (
              <span className="text-xs font-semibold text-[var(--foreground)]">{title}</span>
            )}
            {tabs}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}

      {summary && summary.length > 0 && (
        <div className="flex items-center gap-4 border-b border-[var(--border)] bg-[var(--card)] px-3 py-2">
          {summary.map((item) => (
            <div key={item.label} className="flex items-baseline gap-1.5">
              <span className="text-[10px] text-[var(--muted-foreground)]">{item.label}</span>
              <span
                className="font-mono text-xs font-semibold"
                style={item.color ? { color: item.color } : undefined}
              >
                {item.value}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="bg-[var(--card)]">{children}</div>
    </div>
  );
}

/** Toolbar tab button for use inside {@link SectionPanel}'s `tabs` prop. */
export function ToolbarTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
        active
          ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
          : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      }`}
    >
      {label}
    </button>
  );
}
