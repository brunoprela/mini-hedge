"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cn } from "@/shared/lib/cn";
import { eodStatusQueryOptions } from "../api";

const STEP_LABELS: Record<string, string> = {
  market_close: "Market Close",
  price_finalization: "Price Finalization",
  position_recon: "Position Reconciliation",
  nav_calculation: "NAV Calculation",
  fee_accrual: "Fee Accrual",
  pnl_snapshot: "P&L Snapshot",
  capital_allocation: "Capital Allocation",
  eod_risk: "EOD Risk",
  performance_attribution: "Performance Attribution",
};

const STATUS_STYLES: Record<string, string> = {
  completed: "bg-emerald-400/20 text-emerald-400",
  failed: "bg-red-400/20 text-red-400",
  running: "bg-blue-400/20 text-blue-400",
  pending: "bg-zinc-400/20 text-zinc-400",
  skipped: "bg-zinc-400/10 text-zinc-500",
};

export function EODRunStatus({ businessDate }: { businessDate: string }) {
  const { fundSlug } = useFundContext();
  const { data: result, isLoading } = useQuery(eodStatusQueryOptions(fundSlug, businessDate));

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading EOD status...</div>;
  }

  if (!result) {
    return (
      <div className="rounded-md border border-[var(--border)] p-8 text-center text-sm text-[var(--muted-foreground)]">
        No EOD run found for {businessDate}.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "inline-block rounded-full px-3 py-1 text-xs font-medium",
            result.is_successful ? STATUS_STYLES.completed : STATUS_STYLES.failed,
          )}
        >
          {result.is_successful ? "Completed" : "Failed"}
        </span>
        {result.started_at && (
          <span className="text-xs text-[var(--muted-foreground)]">
            Started {new Date(result.started_at).toLocaleTimeString(undefined, { timeZoneName: "short" })}
          </span>
        )}
        {result.completed_at && (
          <span className="text-xs text-[var(--muted-foreground)]">
            &middot; Finished {new Date(result.completed_at).toLocaleTimeString(undefined, { timeZoneName: "short" })}
          </span>
        )}
      </div>

      <div className="space-y-1">
        {result.steps.map((step) => (
          <div
            key={step.step}
            className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-1.5"
          >
            <span className="text-sm">{STEP_LABELS[step.step] ?? step.step}</span>
            <span
              className={cn(
                "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                STATUS_STYLES[step.status] ?? "",
              )}
            >
              {step.status}
            </span>
          </div>
        ))}
      </div>

      {result.steps.some((s) => s.error_message) && (
        <div className="rounded-lg border border-red-400/30 bg-red-400/5 p-3">
          <p className="text-xs font-medium text-red-400">Errors:</p>
          {result.steps
            .filter((s) => s.error_message)
            .map((s) => (
              <p key={s.step} className="mt-1 text-xs text-red-300">
                {STEP_LABELS[s.step]}: {s.error_message}
              </p>
            ))}
        </div>
      )}
    </div>
  );
}
