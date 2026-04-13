"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cn } from "@/shared/lib/cn";
import { hedgeRecommendationsQueryOptions } from "../api";
import type { HedgeRecommendation } from "../types";

function fmtAmount(value: string): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function fmtCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    signDisplay: "never",
  }).format(Math.abs(value));
}

/**
 * Compute the estimated P&L impact (carry cost) of a hedge recommendation.
 *
 * impact = (estimated_cost_bps / 10_000) × notional
 *
 * Positive cost_bps means the hedge has a carry cost (unfavorable).
 * Negative cost_bps means the hedge earns carry (favorable / savings).
 */
function computePnlImpact(rec: HedgeRecommendation): {
  amount: number;
  favorable: boolean;
  label: string;
} {
  const costBps = Number(rec.estimated_cost_bps);
  const notional = Number(rec.notional);
  const amount = (costBps / 10_000) * notional;
  const favorable = amount <= 0;
  const label = favorable
    ? `Saves ${fmtCurrency(amount)}`
    : `Cost ${fmtCurrency(amount)}`;
  return { amount, favorable, label };
}

export function HedgeRecommendations({
  portfolioId,
  onExecuteRecommendation,
}: {
  portfolioId: string;
  onExecuteRecommendation?: (rec: HedgeRecommendation) => void;
}) {
  const { fundSlug } = useFundContext();
  const { data: recs, isLoading } = useQuery(
    hedgeRecommendationsQueryOptions(fundSlug, portfolioId),
  );

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading recommendations...</div>;
  }

  if (!recs || recs.length === 0) {
    return (
      <div className="rounded-md border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        No hedge recommendations. Currency exposure is either fully hedged or below threshold.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--card)]">
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
              Pair
            </th>
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
              Direction
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              Notional
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              Fwd Rate
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              Cost (bps)
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              P&L Impact
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              Tenor
            </th>
            {onExecuteRecommendation && (
              <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                Action
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {recs.map((rec) => (
            <tr
              key={rec.currency_pair}
              className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--sidebar-active)]"
            >
              <td className="px-3 py-1.5 font-medium">{rec.currency_pair}</td>
              <td className="px-3 py-1.5">
                <span
                  className={cn(
                    "inline-block rounded px-1.5 py-0.5 text-xs font-medium",
                    rec.direction === "buy"
                      ? "bg-emerald-400/10 text-emerald-400"
                      : "bg-red-400/10 text-red-400",
                  )}
                >
                  {rec.direction.toUpperCase()}
                </span>
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">{fmtAmount(rec.notional)}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {Number(rec.estimated_forward).toFixed(4)}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">
                {Number(rec.estimated_cost_bps).toFixed(1)}
              </td>
              <td className="px-3 py-1.5 text-right">
                {(() => {
                  const impact = computePnlImpact(rec);
                  return (
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium tabular-nums",
                        impact.favorable
                          ? "bg-(--success)/10 text-(--success)"
                          : "bg-(--destructive)/10 text-(--destructive)",
                      )}
                    >
                      {impact.favorable ? "↓" : "↑"} {impact.label}
                    </span>
                  );
                })()}
              </td>
              <td className="px-3 py-1.5 text-right">{rec.tenor_days}d</td>
              {onExecuteRecommendation && (
                <td className="px-3 py-1.5">
                  <button
                    type="button"
                    onClick={() => onExecuteRecommendation(rec)}
                    className="rounded px-2 py-1 text-xs font-medium text-[var(--primary)] hover:bg-[var(--primary)]/10"
                  >
                    Open Forward
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
