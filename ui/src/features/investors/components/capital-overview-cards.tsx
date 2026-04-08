"use client";

import { useQuery } from "@tanstack/react-query";
import { capitalOverviewQueryOptions } from "@/features/investors/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function CapitalOverviewCards() {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(capitalOverviewQueryOptions(fundSlug));

  if (isLoading || !data) {
    return null;
  }

  const cards = [
    { label: "Total AUM", value: fmt(data.total_aum) },
    { label: "Investors", value: String(data.total_investors) },
    { label: "Shares Outstanding", value: Number(data.total_shares_outstanding).toLocaleString() },
    { label: "Largest Investor", value: pct(data.largest_investor_pct) },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3"
        >
          <p className="text-xs text-[var(--muted-foreground)]">{card.label}</p>
          <p className="mt-0.5 font-mono text-sm font-semibold text-[var(--foreground-bright)]">
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function fmt(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function pct(v: string): string {
  const n = parseFloat(v) * 100;
  if (Number.isNaN(n)) return v;
  return `${n.toFixed(2)}%`;
}
