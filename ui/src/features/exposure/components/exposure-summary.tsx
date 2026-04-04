"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { exposureQueryOptions } from "../api";

export function ExposureSummary({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(exposureQueryOptions(fundSlug, portfolioId));

  if (isLoading || !data) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading exposure...</div>;
  }

  const fmt = (v: string) => {
    const n = parseFloat(v);
    return n.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    });
  };

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard label="Gross" value={fmt(data.gross_exposure)} />
      <StatCard label="Net" value={fmt(data.net_exposure)} />
      <StatCard label="Long" value={fmt(data.long_exposure)} sub={`${data.long_count} positions`} />
      <StatCard
        label="Short"
        value={fmt(data.short_exposure)}
        sub={`${data.short_count} positions`}
      />
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
      {sub && <p className="text-xs text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  );
}
