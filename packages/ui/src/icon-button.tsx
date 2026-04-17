"use client";

/**
 * IconButton — a square button designed for a single icon child.
 * Shares variants with {@link Button} but enforces square sizing and an aria-label.
 */

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible label — required since the button has no visible text. */
  "aria-label": string;
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 border border-transparent",
  secondary:
    "bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] hover:bg-[var(--muted)]",
  ghost:
    "bg-transparent text-[var(--muted-foreground)] border border-transparent hover:bg-[var(--muted)] hover:text-[var(--foreground)]",
  danger:
    "bg-[var(--destructive)] text-white hover:opacity-90 border border-transparent",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-7 w-7",
  md: "h-9 w-9",
  lg: "h-10 w-10",
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { variant = "ghost", size = "md", className = "", type, children, ...rest },
  ref,
) {
  const classes = [
    "inline-flex items-center justify-center rounded-md transition-colors",
    "focus:outline-none focus:ring-2 focus:ring-[var(--ring,theme(colors.blue.500))]",
    "disabled:opacity-50 disabled:cursor-not-allowed",
    VARIANT_CLASSES[variant],
    SIZE_CLASSES[size],
    className,
  ].join(" ");

  return (
    <button ref={ref} type={type ?? "button"} className={classes} {...rest}>
      {children}
    </button>
  );
});
