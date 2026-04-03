"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatPnL, pnlColorClass } from "@/shared/lib/formatters";
import { portfolioSummaryQueryOptions } from "../api";

export function PortfolioSummary({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: summary } = useQuery(portfolioSummaryQueryOptions(fundSlug, portfolioId));

  if (!summary) return null;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <SummaryCard label="Market Value" value={formatPnL(summary.total_market_value)} />
      <SummaryCard label="Cost Basis" value={formatPnL(summary.total_cost_basis)} />
      <SummaryCard
        label="Realized P&L"
        value={formatPnL(summary.total_realized_pnl)}
        className={pnlColorClass(summary.total_realized_pnl)}
      />
      <SummaryCard
        label="Unrealized P&L"
        value={formatPnL(summary.total_unrealized_pnl)}
        className={pnlColorClass(summary.total_unrealized_pnl)}
      />
    </div>
  );
}

function SummaryCard({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className={`mt-1 font-mono text-lg font-semibold ${className}`}>{value}</p>
    </div>
  );
}
