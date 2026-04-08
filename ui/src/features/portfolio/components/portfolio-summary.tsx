"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatPnL } from "@/shared/lib/formatters";
import { portfolioSummaryQueryOptions } from "../api";

/** Returns summary items for use in SectionPanel summary prop. */
export function usePortfolioSummary(portfolioId: string) {
  const { fundSlug } = useFundContext();
  const { data: summary } = useQuery(portfolioSummaryQueryOptions(fundSlug, portfolioId));

  if (!summary) return null;

  const pnlColor = (v: string) => {
    const n = parseFloat(v);
    if (n > 0) return "var(--success)";
    if (n < 0) return "var(--destructive)";
    return undefined;
  };

  return [
    { label: "Market Value", value: formatPnL(summary.total_market_value) },
    { label: "Cost Basis", value: formatPnL(summary.total_cost_basis) },
    {
      label: "Realized P&L",
      value: formatPnL(summary.total_realized_pnl),
      color: pnlColor(summary.total_realized_pnl),
    },
    {
      label: "Unrealized P&L",
      value: formatPnL(summary.total_unrealized_pnl),
      color: pnlColor(summary.total_unrealized_pnl),
    },
  ];
}

/** Standalone component for backward compat — renders as inline strip */
export function PortfolioSummary({ portfolioId }: { portfolioId: string }) {
  const items = usePortfolioSummary(portfolioId);
  if (!items) return null;

  return (
    <div className="flex items-center gap-4 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-[var(--muted-foreground)]">{item.label}</span>
          <span
            className="font-mono text-xs font-semibold"
            style={item.color ? { color: item.color } : undefined}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
