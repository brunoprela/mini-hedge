"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { positionsQueryOptions } from "@/features/portfolio/api";
import { HBarChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function PnLContributors({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: positions, isLoading } = useQuery(positionsQueryOptions(fundSlug, portfolioId));

  const { top, bottom } = useMemo(() => {
    if (!positions || positions.length === 0) return { top: [], bottom: [] };
    const sorted = [...positions]
      .map((p) => ({
        label: p.instrument_id,
        value: Number(p.unrealized_pnl),
      }))
      .sort((a, b) => b.value - a.value);

    return {
      top: sorted.filter((p) => p.value > 0).slice(0, 10),
      bottom: sorted
        .filter((p) => p.value < 0)
        .slice(-10)
        .reverse(),
    };
  }, [positions]);

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>;
  }

  if (!positions || positions.length === 0) return null;

  const panels = [
    { label: "Top Gainers", items: top },
    { label: "Top Losers", items: bottom },
  ].filter((p) => p.items.length > 0);

  if (panels.length === 0) return null;

  return (
    <div className={`grid gap-2 ${panels.length === 2 ? "grid-cols-2" : "grid-cols-1"}`}>
      {panels.map((panel) => (
        <div
          key={panel.label}
          className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3"
        >
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            {panel.label}
          </p>
          <HBarChart items={panel.items} />
        </div>
      ))}
    </div>
  );
}
