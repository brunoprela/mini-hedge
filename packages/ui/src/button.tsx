"use client";

/**
 * Button primitive.
 *
 * Variants: primary (solid), secondary (outlined/muted), ghost (transparent).
 * Sizes: sm, md, lg.
 * Uses CSS variable tokens for theming.
 */

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Optional leading icon rendered before children. */
  leadingIcon?: ReactNode;
  /** Optional trailing icon rendered after children. */
  trailingIcon?: ReactNode;
  /** Show loading state and disable the button. */
  loading?: boolean;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 border border-transparent",
  secondary:
    "bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] hover:bg-[var(--muted)]",
  ghost:
    "bg-transparent text-[var(--foreground)] border border-transparent hover:bg-[var(--muted)]",
  danger:
    "bg-[var(--destructive)] text-white hover:opacity-90 border border-transparent",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3 text-sm gap-2",
  lg: "h-10 px-4 text-sm gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    leadingIcon,
    trailingIcon,
    loading = false,
    disabled,
    className = "",
    children,
    type,
    ...rest
  },
  ref,
) {
  const classes = [
    "inline-flex items-center justify-center rounded-md font-medium transition-colors",
    "focus:outline-none focus:ring-2 focus:ring-[var(--ring,theme(colors.blue.500))] focus:ring-offset-0",
    "disabled:opacity-50 disabled:cursor-not-allowed",
    VARIANT_CLASSES[variant],
    SIZE_CLASSES[size],
    className,
  ].join(" ");

  return (
    <button
      ref={ref}
      type={type ?? "button"}
      disabled={disabled || loading}
      className={classes}
      {...rest}
    >
      {loading ? (
        <span
          className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      ) : (
        leadingIcon
      )}
      {children}
      {!loading && trailingIcon}
    </button>
  );
});
