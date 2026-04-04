"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { InfoTooltip } from "@/shared/components/table-controls";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { brinsonFachlerQueryOptions } from "../api";

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function AttributionSummaryCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();

  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const start = formatDate(thirtyDaysAgo);
  const end = formatDate(today);

  const { data, isLoading } = useQuery(
    brinsonFachlerQueryOptions(fundSlug, portfolioId, start, end),
  );

  const pct = (v: string) => `${(parseFloat(v) * 100).toFixed(2)}%`;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
        Active Return (30d)
        <InfoTooltip text="Portfolio return minus benchmark return over the last 30 days" />
      </p>
      {isLoading ? (
        <p className="mt-1 font-mono text-lg font-semibold text-[var(--muted-foreground)]">--</p>
      ) : data ? (
        <p className="mt-1 font-mono text-lg font-semibold">{pct(data.active_return)}</p>
      ) : (
        <p className="mt-1 font-mono text-lg font-semibold text-[var(--muted-foreground)]">N/A</p>
      )}
      <Link
        href={`/${fundSlug}/attribution`}
        className="mt-2 inline-block text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
      >
        View details &rarr;
      </Link>
    </div>
  );
}
