"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/shared/lib/cn";

interface PortfolioSelectorProps {
  portfolios: { id: string; name: string }[];
  value: string;
  onChange: (id: string) => void;
}

export function PortfolioSelector({ portfolios, value, onChange }: PortfolioSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selected = portfolios.find((p) => p.id === value);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  if (portfolios.length <= 1) return null;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm transition-colors hover:bg-[var(--accent)]",
          open && "border-[var(--primary)]",
        )}
      >
        <span className="text-[var(--foreground)]">{selected?.name ?? "Select portfolio"}</span>
        <ChevronDown className={cn("h-3.5 w-3.5 text-[var(--muted-foreground)] transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[200px] rounded-md border border-[var(--border)] bg-[var(--background-raised)] py-1 shadow-xl">
          {portfolios.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => {
                onChange(p.id);
                setOpen(false);
              }}
              className={cn(
                "block w-full px-3 py-1.5 text-left text-sm transition-colors",
                p.id === value
                  ? "bg-[var(--primary-muted)] font-medium text-[var(--primary)]"
                  : "text-[var(--foreground)] hover:bg-[var(--muted)]",
              )}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
