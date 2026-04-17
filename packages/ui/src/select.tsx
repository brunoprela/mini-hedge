"use client";

/**
 * Select — styled native `<select>` wrapper with token-based theming.
 *
 * For richer combobox behaviour (search, async options) use the `Combobox` primitive.
 */

import { forwardRef, type SelectHTMLAttributes } from "react";

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  /** Display an error ring. */
  invalid?: boolean;
  /** Compact height variant. */
  selectSize?: "sm" | "md";
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { invalid = false, selectSize = "md", className = "", children, ...rest },
  ref,
) {
  const sizeClass = selectSize === "sm" ? "h-8 text-xs" : "h-9 text-sm";
  const ringClass = invalid
    ? "border-[var(--destructive)] focus:ring-[var(--destructive)]"
    : "border-[var(--border)] focus:ring-[var(--ring,var(--primary))]";

  return (
    <select
      ref={ref}
      className={`${sizeClass} w-full rounded-md border ${ringClass} bg-[var(--input,var(--card))] px-2 pr-8 text-[var(--foreground)] focus:outline-none focus:ring-1 ${className}`}
      {...rest}
    >
      {children}
    </select>
  );
});
