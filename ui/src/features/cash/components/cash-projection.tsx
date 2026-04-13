"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatDate } from "@/shared/lib/formatters";
import { cashProjectionQueryOptions, pendingOrdersQueryOptions } from "../api";
import type { CashProjectionEntry } from "../types";

function fmtCurrency(value: string | number): string {
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

/** Estimate cash impact for a pending order's unfilled portion. */
function estimateOrderCash(order: {
  side: string;
  quantity: string | number;
  filled_quantity: string | number;
  limit_price: string | number | null;
  avg_fill_price: string | number | null;
}): number {
  const remaining = Number(order.quantity) - Number(order.filled_quantity);
  if (remaining <= 0) return 0;

  // Use limit price if available, otherwise avg fill price from partial fills
  const price = order.limit_price ? Number(order.limit_price) : Number(order.avg_fill_price ?? 0);
  if (price <= 0) return 0;

  const total = remaining * price;
  // Buy = outflow (negative), Sell = inflow (positive)
  return order.side === "buy" ? -total : total;
}

/** Aggregate pending-order flows keyed by projection_date. */
function buildPendingFlowsByDate(
  orders: Array<{
    side: string;
    quantity: string | number;
    filled_quantity: string | number;
    limit_price: string | number | null;
    avg_fill_price: string | number | null;
  }>,
): { totalPendingInflows: number; totalPendingOutflows: number } {
  let totalPendingInflows = 0;
  let totalPendingOutflows = 0;

  for (const order of orders) {
    const impact = estimateOrderCash(order);
    if (impact > 0) totalPendingInflows += impact;
    else if (impact < 0) totalPendingOutflows += Math.abs(impact);
  }

  return { totalPendingInflows, totalPendingOutflows };
}

export function CashProjection({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const [includePending, setIncludePending] = useState(false);

  const { data, isLoading } = useQuery(cashProjectionQueryOptions(fundSlug, portfolioId));
  const { data: pendingOrders } = useQuery({
    ...pendingOrdersQueryOptions(fundSlug, portfolioId),
    enabled: includePending,
  });

  if (isLoading || !data) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading cash projection...</div>;
  }

  const visibleEntries = data.entries.filter((entry, i) =>
    shouldShowRow(entry, i, data.entries.length),
  );

  if (visibleEntries.length === 0) return null;

  // Compute pending order totals (applied as a lump sum on the first projection day)
  const pendingTotals =
    includePending && pendingOrders
      ? buildPendingFlowsByDate(pendingOrders)
      : { totalPendingInflows: 0, totalPendingOutflows: 0 };

  const hasPendingFlows =
    pendingTotals.totalPendingInflows > 0 || pendingTotals.totalPendingOutflows > 0;

  return (
    <div className="space-y-2">
      {/* Toggle */}
      <label className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
        <button
          type="button"
          role="switch"
          aria-checked={includePending}
          onClick={() => setIncludePending((prev) => !prev)}
          className={`relative inline-flex h-4 w-7 shrink-0 cursor-pointer items-center rounded-full border border-[var(--border)] transition-colors ${
            includePending ? "bg-[var(--primary)]" : "bg-[var(--muted-foreground)]/20"
          }`}
        >
          <span
            className={`inline-block h-3 w-3 rounded-full bg-white transition-transform ${
              includePending ? "translate-x-3.5" : "translate-x-0.5"
            }`}
          />
        </button>
        Include pending orders
      </label>

      {/* Table */}
      <div className="overflow-x-auto rounded-md border border-[var(--border)]">
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

            {/* Pending orders summary row */}
            {includePending && hasPendingFlows && (
              <tr className="border-t-2 border-dashed border-[var(--warning)]">
                <td className="px-3 py-2 text-left text-xs italic text-[var(--warning)]">
                  Est. pending orders
                </td>
                <td className="px-3 py-2 text-right font-mono text-[var(--muted-foreground)]">
                  --
                </td>
                <td className="px-3 py-2 text-right font-mono italic text-[var(--warning)]">
                  {pendingTotals.totalPendingInflows > 0
                    ? fmtCurrency(pendingTotals.totalPendingInflows)
                    : fmtCurrency(0)}
                </td>
                <td className="px-3 py-2 text-right font-mono italic text-[var(--warning)]">
                  {pendingTotals.totalPendingOutflows > 0
                    ? fmtCurrency(pendingTotals.totalPendingOutflows)
                    : fmtCurrency(0)}
                </td>
                <td className="px-3 py-2 text-right font-mono italic text-[var(--warning)]">
                  {fmtCurrency(
                    Number(visibleEntries[visibleEntries.length - 1]?.closing_balance ?? 0) +
                      pendingTotals.totalPendingInflows -
                      pendingTotals.totalPendingOutflows,
                  )}
                </td>
              </tr>
            )}

            {/* Empty pending state */}
            {includePending && pendingOrders && !hasPendingFlows && (
              <tr className="border-t border-dashed border-[var(--border)]">
                <td
                  colSpan={5}
                  className="px-3 py-2 text-center text-xs italic text-[var(--muted-foreground)]"
                >
                  No pending orders with estimable cash impact
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
