"use client";

/**
 * StatusBadge — color-coded state pill.
 * Variants map to CSS variable color tokens so each consumer UI themes them via globals.css.
 */

import type { ReactNode } from "react";

export type StatusVariant =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "neutral"
  | "primary";

const VARIANT_CLASSES: Record<StatusVariant, string> = {
  success:
    "bg-[var(--success-muted,rgba(34,197,94,0.15))] text-[var(--success)]",
  warning:
    "bg-[var(--warning-muted,rgba(245,158,11,0.15))] text-[var(--warning)]",
  danger:
    "bg-[var(--destructive-muted,rgba(239,68,68,0.15))] text-[var(--destructive)]",
  info:
    "bg-[var(--primary-muted,rgba(59,130,246,0.15))] text-[var(--primary)]",
  primary:
    "bg-[var(--primary-muted,rgba(59,130,246,0.15))] text-[var(--primary)]",
  neutral: "bg-[var(--muted)] text-[var(--muted-foreground)]",
};

interface StatusBadgeProps {
  /** Backwards-compat alias for `children`. */
  label?: ReactNode;
  variant?: StatusVariant;
  children?: ReactNode;
  className?: string;
}

export function StatusBadge({
  label,
  variant = "neutral",
  children,
  className = "",
}: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children ?? label}
    </span>
  );
}
