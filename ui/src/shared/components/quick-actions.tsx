"use client";

import { MoreHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export interface QuickAction {
  label: string;
  onClick: () => void;
  variant?: "default" | "danger" | "primary";
  disabled?: boolean;
}

export function QuickActions({ actions }: { actions: QuickAction[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const variantStyles = {
    default: "text-[var(--foreground)] hover:bg-[var(--muted)]",
    danger: "text-[var(--destructive)] hover:bg-[var(--destructive-muted)]",
    primary: "text-[var(--primary)] hover:bg-[var(--primary-muted)]",
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[160px] rounded-md border border-[var(--border)] bg-[var(--background-raised)] py-1 shadow-lg">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              disabled={action.disabled}
              onClick={(e) => {
                e.stopPropagation();
                action.onClick();
                setOpen(false);
              }}
              className={`w-full px-3 py-1.5 text-left text-xs transition-colors disabled:opacity-40 ${variantStyles[action.variant ?? "default"]}`}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
