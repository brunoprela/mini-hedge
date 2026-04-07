"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { fxHedgingSummaryQueryOptions } from "../api";

function fmtNumber(value: string): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function FXSummaryCards({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: summary, isLoading } = useQuery(
    fxHedgingSummaryQueryOptions(fundSlug, portfolioId),
  );

  if (isLoading || !summary) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading FX summary...</div>;
  }

  const cards = [
    { label: "Open Forwards", value: String(summary.total_open_forwards) },
    { label: "Total Notional", value: fmtNumber(summary.total_notional) },
    {
      label: "Net MTM",
      value: fmtNumber(summary.net_mtm),
      color: Number(summary.net_mtm) >= 0 ? "text-emerald-400" : "text-red-400",
    },
    {
      label: "Currencies Hedged",
      value: summary.currencies_hedged.length > 0 ? summary.currencies_hedged.join(", ") : "None",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border border-[var(--border)] p-4">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            {card.label}
          </p>
          <p className={`mt-1 text-xl font-semibold ${"color" in card ? card.color : ""}`}>
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}
