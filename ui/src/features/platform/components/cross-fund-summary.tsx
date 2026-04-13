"use client";

import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { StatusDot } from "@/shared/components/charts";
import { SectionPanel } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { clientFetch } from "@/shared/lib/api";
import { formatPnL, pnlColorClass } from "@/shared/lib/formatters";

// ─── Types ──────────────────────────────────────────────────

interface FundAggregate {
  total_aum: string;
  total_realized_pnl: string;
  total_unrealized_pnl: string;
  portfolio_count: number;
  total_positions: number;
}

// ─── Component ──────────────────────────────────────────────

export function CrossFundSummary() {
  const { fundSlug, funds, isLoading } = useFundContext();
  const [collapsed, setCollapsed] = useState(false);

  // Fetch aggregate data for each fund the user has access to
  const aggregateResults = useQueries({
    queries: funds.map((f) => ({
      queryKey: ["fund-aggregate", f.fund_slug],
      queryFn: () =>
        clientFetch<FundAggregate>("/portfolios/aggregate", {
          fundSlug: f.fund_slug,
        }),
      staleTime: 30_000,
    })),
  });

  const rows = useMemo(() => {
    return funds.map((f, i) => ({
      fund: f,
      aggregate: aggregateResults[i]?.data ?? null,
      isLoading: aggregateResults[i]?.isLoading ?? true,
      isCurrent: f.fund_slug === fundSlug,
    }));
  }, [funds, aggregateResults, fundSlug]);

  // Don't render if only one fund or still loading fund list
  if (isLoading || funds.length <= 1) return null;

  const fmtCurrency = (v: string | number) =>
    Number(v).toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    });

  return (
    <SectionPanel
      title="All Funds"
      actions={
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="text-[10px] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          {collapsed ? "Expand" : "Collapse"}
        </button>
      }
    >
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border)] text-xs">
            <thead>
              <tr>
                <th scope="col" className="whitespace-nowrap px-3 py-1 text-left text-[10px] font-semibold text-[var(--muted-foreground)]">
                  Fund
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 text-right text-[10px] font-semibold text-[var(--muted-foreground)]">
                  Total AUM
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 text-right text-[10px] font-semibold text-[var(--muted-foreground)]">
                  Unrealized P&L
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 text-right text-[10px] font-semibold text-[var(--muted-foreground)]">
                  Realized P&L
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 text-right text-[10px] font-semibold text-[var(--muted-foreground)]">
                  Portfolios
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 text-right text-[10px] font-semibold text-[var(--muted-foreground)]">
                  Positions
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 text-center text-[10px] font-semibold text-[var(--muted-foreground)]">
                  Role
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {rows.map(({ fund, aggregate, isLoading: rowLoading, isCurrent }) => (
                <tr
                  key={fund.fund_slug}
                  className={`transition-colors hover:bg-[var(--table-row-hover)] ${
                    isCurrent ? "bg-[var(--primary-muted)]/30" : ""
                  }`}
                >
                  <td className="px-3 py-1">
                    <div className="flex items-center gap-1.5">
                      {isCurrent && <StatusDot variant="success" size={5} />}
                      <Link
                        href={`/${fund.fund_slug}`}
                        className={`font-medium hover:text-[var(--primary)] ${
                          isCurrent
                            ? "text-[var(--foreground-bright)]"
                            : "text-[var(--foreground)]"
                        }`}
                      >
                        {fund.fund_name}
                      </Link>
                    </div>
                  </td>
                  <td className="px-3 py-1 text-right font-mono">
                    {rowLoading ? (
                      <span className="text-[var(--muted-foreground)]">...</span>
                    ) : aggregate ? (
                      fmtCurrency(aggregate.total_aum)
                    ) : (
                      "\u2014"
                    )}
                  </td>
                  <td className="px-3 py-1 text-right font-mono">
                    {rowLoading ? (
                      <span className="text-[var(--muted-foreground)]">...</span>
                    ) : aggregate ? (
                      <span className={pnlColorClass(aggregate.total_unrealized_pnl)}>
                        {formatPnL(aggregate.total_unrealized_pnl)}
                      </span>
                    ) : (
                      "\u2014"
                    )}
                  </td>
                  <td className="px-3 py-1 text-right font-mono">
                    {rowLoading ? (
                      <span className="text-[var(--muted-foreground)]">...</span>
                    ) : aggregate ? (
                      <span className={pnlColorClass(aggregate.total_realized_pnl)}>
                        {formatPnL(aggregate.total_realized_pnl)}
                      </span>
                    ) : (
                      "\u2014"
                    )}
                  </td>
                  <td className="px-3 py-1 text-right text-[var(--muted-foreground)]">
                    {rowLoading ? "..." : aggregate?.portfolio_count ?? "\u2014"}
                  </td>
                  <td className="px-3 py-1 text-right text-[var(--muted-foreground)]">
                    {rowLoading ? "..." : aggregate?.total_positions ?? "\u2014"}
                  </td>
                  <td className="px-3 py-1 text-center">
                    <span className="rounded-full bg-[var(--muted)] px-2 py-0.5 text-[9px] font-medium text-[var(--muted-foreground)]">
                      {fund.role}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionPanel>
  );
}
