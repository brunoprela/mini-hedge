"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { portfolioSummaryQueryOptions, portfoliosQueryOptions } from "@/features/portfolio/api";
import type { PortfolioInfo, PortfolioSummary } from "@/features/portfolio/types";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatPnL, pnlColorClass } from "@/shared/lib/formatters";

export function FundOverview({ fundSlug }: { fundSlug: string }) {
  const { fundName, role } = useFundContext();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  // Fetch summaries for all portfolios in parallel
  const summaryResults = useQueries({
    queries: (portfolios ?? []).map((p) => portfolioSummaryQueryOptions(fundSlug, p.id)),
  });
  const summaries = summaryResults
    .map((r) => r.data)
    .filter((d): d is PortfolioSummary => d !== undefined);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{fundName}</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          {role ?? "loading..."} &middot; {portfolios?.length ?? 0} portfolio
          {portfolios?.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Aggregate metrics across all portfolios */}
      {summaries.length > 0 && <AggregateMetrics summaries={summaries} />}

      {/* Portfolio breakdown */}
      {portfolios && portfolios.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-[var(--muted-foreground)]">Portfolios</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {portfolios.map((p) => {
              const summary = summaries.find((s) => s.portfolio_id === p.id);
              return (
                <PortfolioCard key={p.id} fundSlug={fundSlug} portfolio={p} summary={summary} />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function AggregateMetrics({ summaries }: { summaries: PortfolioSummary[] }) {
  const totalMarketValue = summaries.reduce((acc, s) => acc + Number(s.total_market_value), 0);
  const totalCostBasis = summaries.reduce((acc, s) => acc + Number(s.total_cost_basis), 0);
  const totalRealizedPnl = summaries.reduce((acc, s) => acc + Number(s.total_realized_pnl), 0);
  const totalUnrealizedPnl = summaries.reduce((acc, s) => acc + Number(s.total_unrealized_pnl), 0);
  const totalPositions = summaries.reduce((acc, s) => acc + s.position_count, 0);

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <MetricCard label="Total AUM" value={formatPnL(String(totalMarketValue))} />
      <MetricCard label="Cost Basis" value={formatPnL(String(totalCostBasis))} />
      <MetricCard
        label="Realized P&L"
        value={formatPnL(String(totalRealizedPnl))}
        className={pnlColorClass(String(totalRealizedPnl))}
      />
      <MetricCard
        label="Unrealized P&L"
        value={formatPnL(String(totalUnrealizedPnl))}
        className={pnlColorClass(String(totalUnrealizedPnl))}
      />
      <MetricCard label="Positions" value={String(totalPositions)} />
    </div>
  );
}

function PortfolioCard({
  fundSlug,
  portfolio,
  summary,
}: {
  fundSlug: string;
  portfolio: PortfolioInfo;
  summary?: PortfolioSummary;
}) {
  return (
    <Link
      href={`/${fundSlug}/portfolio/${portfolio.id}`}
      className="rounded-lg border border-[var(--border)] p-4 transition-colors hover:bg-[var(--muted)]"
    >
      <div className="flex items-baseline justify-between">
        <h3 className="font-medium">{portfolio.name}</h3>
        {summary && summary.position_count > 0 && (
          <span className="text-xs text-[var(--muted-foreground)]">
            {summary.position_count} pos
          </span>
        )}
      </div>
      {portfolio.strategy && (
        <p className="text-xs text-[var(--muted-foreground)]">{portfolio.strategy}</p>
      )}
      {summary && Number(summary.total_market_value) > 0 && (
        <div className="mt-2 flex items-baseline justify-between text-sm">
          <span className="font-mono">{formatPnL(summary.total_market_value)}</span>
          <span className={`font-mono text-xs ${pnlColorClass(summary.total_unrealized_pnl)}`}>
            {formatPnL(summary.total_unrealized_pnl)}
          </span>
        </div>
      )}
    </Link>
  );
}

function MetricCard({
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
