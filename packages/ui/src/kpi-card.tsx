"use client";

/**
 * KpiCard — label + value with optional trend/sublabel.
 * Designed to tile inside dashboards and summary strips.
 */

import type { ReactNode } from "react";

export type KpiTrend = "up" | "down" | "flat";

interface KpiCardProps {
  label: string;
  value: ReactNode;
  /** Optional secondary line rendered under the value. */
  sublabel?: ReactNode;
  /** Trend indicator — influences color of sublabel. */
  trend?: KpiTrend;
  /** Optional leading icon (e.g. from lucide-react). */
  icon?: ReactNode;
  /** Override value color. Use CSS variables like `var(--destructive)`. */
  valueColor?: string;
  /** Remove the border (useful when tiling with `gap-px` grid pattern). */
  flat?: boolean;
}

const TREND_COLORS: Record<KpiTrend, string> = {
  up: "text-[var(--success)]",
  down: "text-[var(--destructive)]",
  flat: "text-[var(--muted-foreground)]",
};

export function KpiCard({
  label,
  value,
  sublabel,
  trend,
  icon,
  valueColor,
  flat = false,
}: KpiCardProps) {
  const wrapperClass = flat
    ? "bg-[var(--card)] px-4 py-3"
    : "rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3";

  return (
    <div className={wrapperClass}>
      <div className="flex items-center gap-2">
        {icon && (
          <span className="text-[var(--muted-foreground)]" aria-hidden="true">
            {icon}
          </span>
        )}
        <span className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
          {label}
        </span>
      </div>
      <div
        className="mt-1 font-mono text-lg font-bold"
        style={valueColor ? { color: valueColor } : undefined}
      >
        {value}
      </div>
      {sublabel && (
        <div
          className={`mt-0.5 text-[10px] ${
            trend ? TREND_COLORS[trend] : "text-[var(--muted-foreground)]"
          }`}
        >
          {sublabel}
        </div>
      )}
    </div>
  );
}
