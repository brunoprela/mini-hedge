"use client";

import { useQuery } from "@tanstack/react-query";
import { LoadingSkeleton } from "@mini-hedge/ui";
import { capitalAccountsQueryOptions } from "@/features/investors/api";
import { DonutChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const MAX_SLICES = 7;

export function NavAllocationChart() {
  const { fundSlug } = useFundContext();
  const { data: accounts, isLoading } = useQuery(capitalAccountsQueryOptions(fundSlug));

  if (isLoading) {
    return (
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
        <LoadingSkeleton height="11rem" />
      </div>
    );
  }

  if (!accounts?.length) return null;

  // Build segments from ending_capital, sorted descending
  const parsed = accounts
    .map((a) => ({
      label: a.investor_name,
      value: Math.max(parseFloat(a.ending_capital) || 0, 0),
    }))
    .filter((s) => s.value > 0)
    .sort((a, b) => b.value - a.value);

  if (parsed.length === 0) return null;

  // Group beyond MAX_SLICES into "Others"
  let segments: { label: string; value: number; color: string }[];
  if (parsed.length <= MAX_SLICES) {
    segments = parsed.map((s) => ({ ...s, color: "" }));
  } else {
    const top = parsed.slice(0, MAX_SLICES - 1);
    const othersValue = parsed.slice(MAX_SLICES - 1).reduce((sum, s) => sum + s.value, 0);
    segments = [
      ...top.map((s) => ({ ...s, color: "" })),
      { label: "Others", value: othersValue, color: "" },
    ];
  }

  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const centerValue = total >= 1_000_000
    ? `$${(total / 1_000_000).toFixed(1)}M`
    : `$${(total / 1_000).toFixed(0)}K`;

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
        NAV Allocation by Investor
      </h3>
      <DonutChart
        segments={segments}
        size={180}
        thickness={32}
        centerLabel="Total NAV"
        centerValue={centerValue}
      />
    </div>
  );
}
