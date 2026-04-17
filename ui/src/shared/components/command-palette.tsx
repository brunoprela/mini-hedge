"use client";

import { type CommandPaletteGroup, CommandPalette as UICommandPalette } from "@mini-hedge/ui";
import { useQuery } from "@tanstack/react-query";
import { Briefcase, LayoutDashboard, Moon, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { PortfolioInfo } from "@/features/portfolio/types";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTheme } from "@/shared/hooks/use-theme";
import { api, fundHeaders } from "@/shared/lib/api-client";
import { NAV_ITEMS } from "@/shared/lib/navigation";

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

  const { data: portfolios = [] } = useQuery<PortfolioInfo[]>({
    queryKey: ["portfolios", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/portfolios", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return (data ?? []) as unknown as PortfolioInfo[];
    },
    staleTime: 60_000,
    enabled: open,
  });

  const groups = useMemo<CommandPaletteGroup[]>(() => {
    const lower = query.toLowerCase();
    const matches = (label: string) => !query || label.toLowerCase().includes(lower);

    const navItems = NAV_ITEMS.filter((item) => !item.permission || can(item.permission))
      .filter((item) => matches(item.label))
      .map((item) => ({
        id: `nav-${item.href || "dashboard"}`,
        label: item.label,
        icon: <LayoutDashboard className="h-4 w-4" />,
        onSelect: () => {
          router.push(`/${fundSlug}${item.href}`);
          onOpenChange(false);
        },
      }));

    const portfolioItems = portfolios
      .filter((p) => matches(p.name))
      .map((p) => ({
        id: `portfolio-${p.id}`,
        label: p.name,
        icon: <Briefcase className="h-4 w-4" />,
        onSelect: () => {
          router.push(`/${fundSlug}/portfolio/${p.slug}`);
          onOpenChange(false);
        },
      }));

    const actionItems = [
      {
        id: "action-toggle-theme",
        label: `Switch to ${theme === "dark" ? "light" : "dark"} mode`,
        icon: theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />,
        onSelect: () => {
          toggleTheme();
          onOpenChange(false);
        },
      },
    ].filter((item) => matches(item.label));

    return [
      { category: "Navigation", items: navItems },
      { category: "Portfolios", items: portfolioItems },
      { category: "Actions", items: actionItems },
    ];
  }, [can, fundSlug, onOpenChange, portfolios, query, router, theme, toggleTheme]);

  // Reset query when closing
  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  return (
    <UICommandPalette
      open={open}
      onClose={(next) => onOpenChange(next)}
      query={query}
      onQueryChange={setQuery}
      groups={groups}
      placeholder="Type a command or search..."
    />
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
