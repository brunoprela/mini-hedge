"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo } from "react";
import { LoadingSkeleton } from "@mini-hedge/ui";
import { violationsQueryOptions } from "@/features/compliance/api";
import { ordersQueryOptions } from "@/features/orders/api";
import { portfolioSummaryQueryOptions, portfoliosQueryOptions } from "@/features/portfolio/api";
import type { PortfolioInfo, PortfolioSummary } from "@/features/portfolio/types";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatPnL, pnlColorClass } from "@/shared/lib/formatters";

export function FundOverview({ fundSlug }: { fundSlug: string }) {
  const { fundName, role } = useFundContext();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  const firstPortfolioId = portfolios?.[0]?.id ?? "";

  const summaryResults = useQueries({
    queries: (portfolios ?? []).map((p) => portfolioSummaryQueryOptions(fundSlug, p.id)),
  });
  const summaries = summaryResults
    .map((r) => r.data)
    .filter((d): d is PortfolioSummary => d !== undefined);

  // Operational data for widgets
  const { data: orders } = useQuery({
    ...ordersQueryOptions(fundSlug, firstPortfolioId),
    enabled: !!firstPortfolioId,
  });
  const { data: violations } = useQuery({
    ...violationsQueryOptions(fundSlug, firstPortfolioId),
    enabled: !!firstPortfolioId,
  });

  const orderStats = useMemo(() => {
    if (!orders) return null;
    const today = new Date().toISOString().slice(0, 10);
    const todayOrders = orders.filter((o) => o.created_at.slice(0, 10) === today);
    return {
      total: todayOrders.length,
      filled: todayOrders.filter((o) => o.state === "filled").length,
      working: todayOrders.filter((o) => ["working", "partially_filled", "sent"].includes(o.state))
        .length,
      rejected: todayOrders.filter((o) => o.state === "rejected").length,
    };
  }, [orders]);

  const complianceStats = useMemo(() => {
    if (!violations) return null;
    return {
      total: violations.length,
      blocks: violations.filter((v) => v.severity === "block").length,
      warnings: violations.filter((v) => v.severity === "warning").length,
    };
  }, [violations]);

  const totalAUM = summaries.reduce((acc, s) => acc + Number(s.total_market_value), 0);
  const totalPnL = summaries.reduce((acc, s) => acc + Number(s.total_unrealized_pnl), 0);
  const totalPositions = summaries.reduce((acc, s) => acc + s.position_count, 0);

  return (
    <div className="space-y-3">
      {/* Greeting */}
      <div>
        <h1 className="text-lg font-semibold text-[var(--foreground-bright)]">{fundName}</h1>
        <p className="text-xs text-[var(--muted-foreground)]">
          {role ?? "loading..."} &middot; {portfolios?.length ?? 0} portfolio
          {portfolios?.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Widget grid — operational dashboard */}
      <div className="grid grid-cols-12 gap-3">
        {/* AUM & P&L summary widget */}
        <div className="col-span-4 rounded-md border border-[var(--border)] bg-[var(--card)]">
          <div className="border-b border-[var(--border)] bg-[var(--primary-muted)] px-3 py-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--foreground)]">
              Fund Summary
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 p-3">
            <div>
              <p className="text-[10px] text-[var(--muted-foreground)]">Total AUM</p>
              <p className="font-mono text-sm font-semibold">{formatPnL(String(totalAUM))}</p>
            </div>
            <div>
              <p className="text-[10px] text-[var(--muted-foreground)]">Unrealized P&L</p>
              <p className={`font-mono text-sm font-semibold ${pnlColorClass(String(totalPnL))}`}>
                {formatPnL(String(totalPnL))}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-[var(--muted-foreground)]">Positions</p>
              <p className="font-mono text-sm font-semibold">{totalPositions}</p>
            </div>
            <div>
              <p className="text-[10px] text-[var(--muted-foreground)]">Portfolios</p>
              <p className="font-mono text-sm font-semibold">{portfolios?.length ?? 0}</p>
            </div>
          </div>
        </div>

        {/* Today's Orders widget */}
        <div className="col-span-4 rounded-md border border-[var(--border)] bg-[var(--card)]">
          <div className="border-b border-[var(--border)] bg-[var(--primary-muted)] px-3 py-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--foreground)]">
              Today&apos;s Orders
            </span>
          </div>
          <div className="p-3">
            {orderStats ? (
              <div className="flex items-center gap-3">
                <CountBadge count={orderStats.total} label="Total" color="var(--foreground)" />
                <CountBadge count={orderStats.filled} label="Filled" color="var(--success)" />
                <CountBadge count={orderStats.working} label="Working" color="var(--primary)" />
                <CountBadge
                  count={orderStats.rejected}
                  label="Rejected"
                  color="var(--destructive)"
                />
              </div>
            ) : (
              <p className="text-xs text-[var(--muted-foreground)]">No orders data</p>
            )}
            <Link
              href={`/${fundSlug}/orders`}
              className="mt-2 inline-block text-[10px] text-[var(--primary)] hover:underline"
            >
              View Order Blotter &rarr;
            </Link>
          </div>
        </div>

        {/* Compliance widget */}
        <div className="col-span-4 rounded-md border border-[var(--border)] bg-[var(--card)]">
          <div className="border-b border-[var(--border)] bg-[var(--primary-muted)] px-3 py-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--foreground)]">
              Compliance
            </span>
          </div>
          <div className="p-3">
            {complianceStats ? (
              complianceStats.total === 0 ? (
                <p className="text-xs text-[var(--success)]">All clear — no violations</p>
              ) : (
                <div className="flex items-center gap-3">
                  <CountBadge
                    count={complianceStats.total}
                    label="Active"
                    color="var(--foreground)"
                  />
                  <CountBadge
                    count={complianceStats.blocks}
                    label="Blocks"
                    color="var(--destructive)"
                  />
                  <CountBadge
                    count={complianceStats.warnings}
                    label="Warnings"
                    color="var(--warning)"
                  />
                </div>
              )
            ) : (
              <LoadingSkeleton variant="text" rows={2} />
            )}
            <Link
              href={`/${fundSlug}/compliance`}
              className="mt-2 inline-block text-[10px] text-[var(--primary)] hover:underline"
            >
              View Compliance &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Portfolios table */}
      {portfolios && portfolios.length > 0 && (
        <div className="overflow-hidden rounded-md border border-[var(--border)]">
          <div className="border-b border-[var(--border)] bg-[var(--primary-muted)] px-3 py-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--foreground)]">
              Portfolios
            </span>
          </div>
          <table className="min-w-full divide-y divide-[var(--border)] text-sm">
            <thead>
              <tr>
                <th scope="col" className="whitespace-nowrap px-3 py-1.5 text-left text-xs font-semibold text-[var(--muted-foreground)]">
                  Portfolio
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1.5 text-right text-xs font-semibold text-[var(--muted-foreground)]">
                  NAV
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1.5 text-right text-xs font-semibold text-[var(--muted-foreground)]">
                  P&L
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1.5 text-right text-xs font-semibold text-[var(--muted-foreground)]">
                  Positions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {portfolios.map((p) => {
                const summary = summaries.find((s) => s.portfolio_id === p.id);
                return (
                  <PortfolioRow key={p.id} fundSlug={fundSlug} portfolio={p} summary={summary} />
                );
              })}
            </tbody>
          </table>
        </div>
      )}
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
    <tr className="transition-colors hover:bg-[var(--table-row-hover)]">
      <td className="px-3 py-1.5">
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
      <td className="px-3 py-1.5 text-right font-mono text-sm">
        {summary ? formatPnL(summary.total_market_value) : "—"}
      </td>
      <td className="px-3 py-1.5 text-right">
        {summary ? (
          <span className={`font-mono text-sm ${pnlColorClass(summary.total_unrealized_pnl)}`}>
            {formatPnL(summary.total_unrealized_pnl)}
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="px-3 py-1.5 text-right text-sm text-[var(--muted-foreground)]">
        {summary?.position_count ?? "—"}
      </td>
    </tr>
  );
}

function CountBadge({ count, label, color }: { count: number; label: string; color: string }) {
  return (
    <div className="text-center">
      <p className="font-mono text-lg font-bold" style={{ color }}>
        {count}
      </p>
      <p className="text-[9px] uppercase tracking-wider text-[var(--muted-foreground)]">{label}</p>
    </div>
  );
}
