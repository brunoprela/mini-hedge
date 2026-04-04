"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatDate } from "@/shared/lib/formatters";
import { cashProjectionQueryOptions } from "../api";
import type { CashProjectionEntry } from "../types";

function fmtCurrency(value: string): string {
  return Number(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function shouldShowRow(entry: CashProjectionEntry, index: number, total: number): boolean {
  if (index === 0 || index === total - 1) return true;
  if (Number(entry.inflows) > 0 || Number(entry.outflows) > 0) return true;
  return false;
}

export function CashProjection({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(cashProjectionQueryOptions(fundSlug, portfolioId));

  if (isLoading || !data) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading cash projection...</div>;
  }

  const visibleEntries = data.entries.filter((entry, i) =>
    shouldShowRow(entry, i, data.entries.length),
  );

  if (visibleEntries.length === 0) {
    return <div className="text-sm text-[var(--muted-foreground)]">No projection data.</div>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--muted-foreground)]/5">
            <th className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)]">
              Date
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
              Opening
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
              Inflows
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
              Outflows
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
              Closing
            </th>
          </tr>
        </thead>
        <tbody>
          {visibleEntries.map((entry) => (
            <tr
              key={`${entry.projection_date}-${entry.currency}`}
              className="border-b border-[var(--border)] last:border-b-0"
            >
              <td className="px-3 py-2 text-left">{formatDate(entry.projection_date)}</td>
              <td className="px-3 py-2 text-right font-mono">
                {fmtCurrency(entry.opening_balance)}
              </td>
              <td className="px-3 py-2 text-right font-mono text-[var(--success)]">
                {fmtCurrency(entry.inflows)}
              </td>
              <td className="px-3 py-2 text-right font-mono text-[var(--destructive)]">
                {fmtCurrency(entry.outflows)}
              </td>
              <td className="px-3 py-2 text-right font-mono font-semibold">
                {fmtCurrency(entry.closing_balance)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
