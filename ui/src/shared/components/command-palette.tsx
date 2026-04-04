"use client";

import { useQuery } from "@tanstack/react-query";
import { Briefcase, LayoutDashboard, Moon, Search, Sun, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PortfolioInfo } from "@/features/portfolio/types";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTheme } from "@/shared/hooks/use-theme";
import { clientFetch } from "@/shared/lib/api";
import { NAV_ITEMS } from "@/shared/lib/navigation";

interface CommandItem {
  id: string;
  label: string;
  category: "Navigation" | "Portfolios" | "Actions";
  onSelect: () => void;
  icon?: React.ReactNode;
}

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const { theme, toggle: toggleTheme } = useTheme();

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: portfolios = [] } = useQuery<PortfolioInfo[]>({
    queryKey: ["portfolios", fundSlug],
    queryFn: () => clientFetch<PortfolioInfo[]>("/portfolios", { fundSlug }),
    staleTime: 60_000,
    enabled: open,
  });

  const items = useMemo<CommandItem[]>(() => {
    const navItems: CommandItem[] = NAV_ITEMS.filter(
      (item) => !item.permission || can(item.permission),
    ).map((item) => ({
      id: `nav-${item.href || "dashboard"}`,
      label: item.label,
      category: "Navigation",
      icon: <LayoutDashboard className="h-4 w-4" />,
      onSelect: () => {
        router.push(`/${fundSlug}${item.href}`);
        onOpenChange(false);
      },
    }));

    const portfolioItems: CommandItem[] = portfolios.map((p) => ({
      id: `portfolio-${p.id}`,
      label: p.name,
      category: "Portfolios",
      icon: <Briefcase className="h-4 w-4" />,
      onSelect: () => {
        router.push(`/${fundSlug}/portfolio/${p.slug}`);
        onOpenChange(false);
      },
    }));

    const actionItems: CommandItem[] = [
      {
        id: "action-toggle-theme",
        label: `Switch to ${theme === "dark" ? "light" : "dark"} mode`,
        category: "Actions",
        icon: theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />,
        onSelect: () => {
          toggleTheme();
          onOpenChange(false);
        },
      },
    ];

    return [...navItems, ...portfolioItems, ...actionItems];
  }, [can, fundSlug, onOpenChange, portfolios, router, theme, toggleTheme]);

  const filtered = useMemo(() => {
    if (!query) return items;
    const lower = query.toLowerCase();
    return items.filter((item) => item.label.toLowerCase().includes(lower));
  }, [items, query]);

  const grouped = useMemo(() => {
    const groups: { category: string; items: CommandItem[] }[] = [];
    for (const item of filtered) {
      const existing = groups.find((g) => g.category === item.category);
      if (existing) {
        existing.items.push(item);
      } else {
        groups.push({ category: item.category, items: [item] });
      }
    }
    return groups;
  }, [filtered]);

  // Reset state when opening/closing
  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Reset active index when filtered results change
  const filteredCount = filtered.length;
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional trigger on count change
  useEffect(() => {
    setActiveIndex(0);
  }, [filteredCount]);

  // Scroll active item into view
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional trigger on index change
  useEffect(() => {
    if (!listRef.current) return;
    const active = listRef.current.querySelector("[data-active='true']");
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        filtered[activeIndex]?.onSelect();
      } else if (e.key === "Escape") {
        e.preventDefault();
        onOpenChange(false);
      }
    },
    [activeIndex, filtered, onOpenChange],
  );

  const handleBackdropClick = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  if (!open) return null;

  let flatIndex = -1;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close command palette"
        className="absolute inset-0 bg-black/50"
        onClick={handleBackdropClick}
        tabIndex={-1}
      />

      {/* Palette */}
      <div
        role="dialog"
        aria-label="Command palette"
        className="relative w-full max-w-lg overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-2xl"
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] px-4">
          <Search className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="h-12 flex-1 bg-transparent text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none"
          />
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="flex h-6 w-6 items-center justify-center rounded text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
              No results found.
            </div>
          ) : (
            grouped.map((group) => (
              <div key={group.category} className="mb-1">
                <div className="px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                  {group.category}
                </div>
                {group.items.map((item) => {
                  flatIndex++;
                  const isActive = flatIndex === activeIndex;
                  const idx = flatIndex;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      data-active={isActive}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                        isActive
                          ? "bg-[var(--primary)] text-white"
                          : "text-[var(--foreground)] hover:bg-[var(--muted)]"
                      }`}
                      onClick={item.onSelect}
                      onMouseEnter={() => setActiveIndex(idx)}
                    >
                      <span className={isActive ? "text-white" : "text-[var(--muted-foreground)]"}>
                        {item.icon}
                      </span>
                      {item.label}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--muted-foreground)]">
          <span>
            <kbd className="rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px]">
              &uarr;&darr;
            </kbd>{" "}
            navigate
          </span>
          <span>
            <kbd className="rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px]">
              Enter
            </kbd>{" "}
            select
          </span>
          <span>
            <kbd className="rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px]">
              Esc
            </kbd>{" "}
            close
          </span>
        </div>
      </div>
    </div>
  );
}

/** Global keyboard shortcut hook for Cmd+K / Ctrl+K */
export function useCommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return { open, setOpen } as const;
}
