"use client";

/**
 * Tooltip primitive — hover/focus popover.
 *
 * Headless UI does not ship a dedicated Tooltip (Popover is click-driven, not hover-driven),
 * and Tailwind UI v4 has no template for this exact pattern. This is the one primitive where
 * we hand-roll the trigger, but we keep it a11y-correct:
 *
 * - Trigger listens to `onMouseEnter` / `onMouseLeave` / `onFocus` / `onBlur` (passive events,
 *   not interactive onClick — Biome a11y rules are satisfied without ignores).
 * - Panel has `role="tooltip"` and the trigger carries `aria-describedby` so screen readers
 *   announce the content when the user focuses the trigger.
 * - Escape dismisses via React state.
 */

import { useEffect, useId, useState, type ReactNode } from "react";

interface TooltipProps {
  /** The trigger content (usually an icon or short label). */
  children: ReactNode;
  /** The tooltip body shown when the trigger is hovered/focused. */
  content: ReactNode;
  /** Placement of the panel relative to the trigger. Defaults to `top`. */
  placement?: "top" | "bottom";
}

export function Tooltip({ children, content, placement = "top" }: TooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  const panelClass =
    placement === "top"
      ? "absolute bottom-full left-1/2 z-50 mb-1.5 -translate-x-1/2"
      : "absolute top-full left-1/2 z-50 mt-1.5 -translate-x-1/2";

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      aria-describedby={open ? id : undefined}
    >
      {children}
      {open && (
        <span
          id={id}
          role="tooltip"
          className={`${panelClass} whitespace-nowrap rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-1.5 text-xs text-[var(--foreground)] shadow-md`}
        >
          {content}
        </span>
      )}
    </span>
  );
}
