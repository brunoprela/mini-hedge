"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { cn } from "@/shared/lib/cn";
import { Permission } from "@/shared/lib/permissions";
import type { EODStepResult } from "../types";
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

function formatDuration(startedAt: string, completedAt: string | null | undefined): string | null {
  if (!completedAt) return null;
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined) return "--";
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function StepRow({ step }: { step: EODStepResult }) {
  const [expanded, setExpanded] = useState(false);

  const duration = formatDuration(step.started_at, step.completed_at);
  const hasDetails = step.details && Object.keys(step.details).length > 0;
  const hasError = !!step.error_message;
  const hasExtra = hasDetails || hasError || duration !== null;

  return (
    <div className="border border-[var(--border)] rounded-md">
      <button
        type="button"
        onClick={() => hasExtra && setExpanded((prev) => !prev)}
        className={cn(
          "flex w-full items-center justify-between px-3 py-1.5 text-left",
          hasExtra && "cursor-pointer hover:bg-[var(--card)]",
          !hasExtra && "cursor-default",
        )}
      >
        <span className="flex items-center gap-2 text-sm">
          {hasExtra ? (
            expanded ? (
              <ChevronDown className="h-3.5 w-3.5 text-[var(--muted-foreground)] shrink-0" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-[var(--muted-foreground)] shrink-0" />
            )
          ) : (
            <span className="inline-block w-3.5" />
          )}
          {STEP_LABELS[step.step] ?? step.step}
        </span>
        <span className="flex items-center gap-2">
          {duration !== null && (
            <span className="text-xs tabular-nums text-[var(--muted-foreground)]">{duration}</span>
          )}
          <span
            className={cn(
              "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
              STATUS_STYLES[step.status] ?? "",
            )}
          >
            {step.status}
          </span>
        </span>
      </button>

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-in-out",
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <div className="border-t border-[var(--border)] px-3 py-2 ml-6 space-y-2">
            {/* Timing */}
            <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-[var(--muted-foreground)]">
              <span>
                Started:{" "}
                {new Date(step.started_at).toLocaleTimeString(undefined, {
                  timeZoneName: "short",
                })}
              </span>
              {step.completed_at && (
                <span>
                  Completed:{" "}
                  {new Date(step.completed_at).toLocaleTimeString(undefined, {
                    timeZoneName: "short",
                  })}
                </span>
              )}
              {duration !== null && <span>Duration: {duration}</span>}
            </div>

            {/* Error */}
            {hasError && (
              <div className="rounded border border-red-400/30 bg-red-400/5 px-2.5 py-1.5">
                <p className="text-xs font-medium text-red-400">Error</p>
                <p className="mt-0.5 text-xs text-red-300">{step.error_message}</p>
              </div>
            )}

            {/* Details */}
            {hasDetails && (
              <div className="space-y-0.5">
                <p className="text-xs font-medium text-[var(--muted-foreground)]">Details</p>
                <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                  {Object.entries(step.details!).map(([key, value]) => (
                    <div key={key} className="contents">
                      <span className="text-[var(--muted-foreground)]">{key}</span>
                      <span className="text-[var(--foreground)] tabular-nums">
                        {formatDetailValue(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

interface EODRunStatusProps {
  businessDate: string;
  onRerun?: (businessDate: string) => void;
  isRerunPending?: boolean;
}

export function EODRunStatus({ businessDate, onRerun, isRerunPending }: EODRunStatusProps) {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const { data: result, isLoading } = useQuery(eodStatusQueryOptions(fundSlug, businessDate));
  const [showConfirm, setShowConfirm] = useState(false);

  const canRerun = can(Permission.EOD_RUN);
  const isTerminal = result != null && result.completed_at != null;

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
            Started{" "}
            {new Date(result.started_at).toLocaleTimeString(undefined, { timeZoneName: "short" })}
          </span>
        )}
        {result.completed_at && (
          <span className="text-xs text-[var(--muted-foreground)]">
            &middot; Finished{" "}
            {new Date(result.completed_at).toLocaleTimeString(undefined, { timeZoneName: "short" })}
          </span>
        )}

        {/* Re-run button (ops/admin only, terminal runs only) */}
        {canRerun && isTerminal && onRerun && (
          <div className="ml-auto flex items-center gap-2">
            {showConfirm ? (
              <div className="flex items-center gap-2 rounded-md border border-[var(--warning)]/40 bg-[var(--warning)]/5 px-2.5 py-1">
                <AlertTriangle className="h-3.5 w-3.5 text-[var(--warning)]" />
                <span className="text-xs text-[var(--warning)]">
                  Re-run EOD for {businessDate}? This will overwrite existing results.
                </span>
                <button
                  type="button"
                  onClick={() => {
                    onRerun(businessDate);
                    setShowConfirm(false);
                  }}
                  disabled={isRerunPending}
                  className="rounded bg-[var(--warning)] px-2 py-0.5 text-xs font-medium text-black hover:opacity-90 disabled:opacity-50"
                >
                  {isRerunPending ? "Running..." : "Confirm"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowConfirm(false)}
                  className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowConfirm(true)}
                disabled={isRerunPending}
                className="flex items-center gap-1.5 rounded-md border border-[var(--warning)]/40 px-2.5 py-1 text-xs font-medium text-[var(--warning)] hover:bg-[var(--warning)]/10 disabled:opacity-50"
              >
                <RotateCcw className="h-3 w-3" />
                Re-run
              </button>
            )}
          </div>
        )}
      </div>

      <div className="space-y-1">
        {result.steps.map((step) => (
          <StepRow key={step.step} step={step} />
        ))}
      </div>
    </div>
  );
}
