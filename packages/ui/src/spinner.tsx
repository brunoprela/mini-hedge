"use client";

/**
 * Spinner — small indeterminate loading indicator.
 * Inherits color via `currentColor` so it picks up its parent's text color.
 */

type Size = "xs" | "sm" | "md" | "lg";

const SIZE_CLASSES: Record<Size, string> = {
  xs: "h-3 w-3 border",
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-8 w-8 border-[3px]",
};

export function Spinner({
  size = "sm",
  className = "",
  label = "Loading",
}: {
  size?: Size;
  className?: string;
  /** Screen-reader label. Defaults to "Loading". */
  label?: string;
}) {
  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-block animate-spin rounded-full border-current border-t-transparent ${SIZE_CLASSES[size]} ${className}`}
    >
      <span className="sr-only">{label}</span>
    </span>
  );
}
