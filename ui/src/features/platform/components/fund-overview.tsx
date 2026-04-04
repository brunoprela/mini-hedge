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

  const summaryResults = useQueries({
    queries: (portfolios ?? []).map((p) => portfolioSummaryQueryOptions(fundSlug, p.id)),
  });
  const summaries = summaryResults
    .map((r) => r.data)
    .filter((d): d is PortfolioSummary => d !== undefined);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">{fundName}</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          {role ?? "loading..."} &middot; {portfolios?.length ?? 0} portfolio
          {portfolios?.length !== 1 ? "s" : ""}
        </p>
      </div>

      {summaries.length > 0 && <AggregateMetrics summaries={summaries} />}

      {portfolios && portfolios.length > 0 && (
        <div>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Portfolios
          </h2>
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)]">
                    Portfolio
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)]">
                    NAV
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)]">
                    P&L
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)]">
                    Positions
                  </th>
                </tr>
              </thead>
              <tbody>
                {portfolios.map((p) => {
                  const summary = summaries.find((s) => s.portfolio_id === p.id);
                  return (
                    <PortfolioRow key={p.id} fundSlug={fundSlug} portfolio={p} summary={summary} />
                  );
                })}
              </tbody>
            </table>
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
        valueClass={pnlColorClass(String(totalRealizedPnl))}
      />
      <MetricCard
        label="Unrealized P&L"
        value={formatPnL(String(totalUnrealizedPnl))}
        valueClass={pnlColorClass(String(totalUnrealizedPnl))}
      />
      <MetricCard label="Positions" value={String(totalPositions)} />
    </div>
  );
}

function PortfolioRow({
  fundSlug,
  portfolio,
  summary,
}: {
  fundSlug: string;
  portfolio: PortfolioInfo;
  summary?: PortfolioSummary;
}) {
  return (
    <tr className="border-b border-[var(--table-border)] last:border-0 transition-colors hover:bg-[var(--table-row-hover)]">
      <td className="px-4 py-3">
        <Link
          href={`/${fundSlug}/portfolio/${portfolio.id}`}
          className="font-medium text-[var(--foreground-bright)] hover:text-[var(--primary)]"
        >
          {portfolio.name}
        </Link>
        {portfolio.strategy && (
          <p className="text-xs text-[var(--muted-foreground)]">{portfolio.strategy}</p>
        )}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm">
        {summary ? formatPnL(summary.total_market_value) : "—"}
      </td>
      <td className="px-4 py-3 text-right">
        {summary ? (
          <span className={`font-mono text-sm ${pnlColorClass(summary.total_unrealized_pnl)}`}>
            {formatPnL(summary.total_unrealized_pnl)}
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 py-3 text-right text-sm text-[var(--muted-foreground)]">
        {summary?.position_count ?? "—"}
      </td>
    </tr>
  );
}

function MetricCard({
  label,
  value,
  valueClass = "",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className={`mt-1 font-mono text-lg font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}
