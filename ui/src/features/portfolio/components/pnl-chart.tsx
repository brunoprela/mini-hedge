"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { cumulativeQueryOptions } from "@/features/attribution/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function PnLChart({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();

  const end = useMemo(() => formatDate(new Date()), []);
  const start = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return formatDate(d);
  }, []);

  const { data, isLoading } = useQuery(cumulativeQueryOptions(fundSlug, portfolioId, start, end));

  if (isLoading) {
    return <p className="text-sm text-(--muted-foreground)">Loading P&L data...</p>;
  }

  if (!data?.periods || data.periods.length === 0) return null;

  const returns = data.periods.map((p) => ({
    date: p.period_end,
    pnl: parseFloat(p.portfolio_return),
  }));

  const maxAbs = Math.max(...returns.map((r) => Math.abs(r.pnl)), 0.0001);

  return (
    <div className="overflow-x-auto rounded-lg border border-(--border) bg-(--card)">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-(--table-border) bg-(--table-header) text-left text-(--muted-foreground)">
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider">Date</th>
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-right">
              Return
            </th>
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider w-1/2"></th>
          </tr>
        </thead>
        <tbody>
          {returns.map((row) => {
            const pct = (row.pnl / maxAbs) * 100;
            const isPositive = row.pnl >= 0;
            return (
              <tr
                key={row.date}
                className="border-b border-(--table-border) last:border-0 hover:bg-(--table-row-hover)"
              >
                <td className="px-3 py-1.5 text-xs text-(--muted-foreground)">{row.date}</td>
                <td
                  className={`px-3 py-1.5 text-right text-xs font-medium ${
                    isPositive ? "text-(--success)" : "text-(--destructive)"
                  }`}
                >
                  {(row.pnl * 100).toFixed(2)}%
                </td>
                <td className="px-3 py-1.5">
                  <div className="flex items-center h-4">
                    {isPositive ? (
                      <div
                        className="h-2.5 rounded-r bg-(--success) opacity-70"
                        style={{ width: `${Math.abs(pct)}%` }}
                      />
                    ) : (
                      <div className="flex w-full justify-end">
                        <div
                          className="h-2.5 rounded-l bg-(--destructive) opacity-70"
                          style={{ width: `${Math.abs(pct)}%` }}
                        />
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Cumulative summary */}
      <div className="border-t border-(--table-border) bg-(--table-header) px-3 py-2 text-xs text-(--muted-foreground)">
        <span className="font-medium">Cumulative:</span>{" "}
        <span
          className={
            parseFloat(data.cumulative_portfolio_return) >= 0
              ? "text-(--success)"
              : "text-(--destructive)"
          }
        >
          {(parseFloat(data.cumulative_portfolio_return) * 100).toFixed(2)}%
        </span>
        <span className="mx-2">|</span>
        <span className="font-medium">Active:</span>{" "}
        <span
          className={
            parseFloat(data.cumulative_active_return) >= 0
              ? "text-(--success)"
              : "text-(--destructive)"
          }
        >
          {(parseFloat(data.cumulative_active_return) * 100).toFixed(2)}%
        </span>
      </div>
    </div>
  );
}
