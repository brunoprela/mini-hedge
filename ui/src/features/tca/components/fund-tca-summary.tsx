"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { fundTCASummaryQueryOptions } from "../api";

const PERIOD_OPTIONS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
] as const;

function fmtBps(v: string) {
  return parseFloat(v).toFixed(2);
}

function fmtCurrency(v: string) {
  return parseFloat(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function FundTCASummaryCard() {
  const { fundSlug } = useFundContext();
  const [days, setDays] = useState<number>(30);
  const { data: summary, isLoading } = useQuery(fundTCASummaryQueryOptions(fundSlug, days));

  return (
    <div className="space-y-3">
      {/* Period selector */}
      <div className="flex items-center gap-1">
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.days}
            type="button"
            onClick={() => setDays(opt.days)}
            className="rounded-md px-3 py-1 text-xs font-medium transition-colors"
            style={{
              backgroundColor: days === opt.days ? "var(--primary)" : "transparent",
              color: days === opt.days ? "var(--primary-foreground)" : "var(--muted-foreground)",
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="text-sm text-[var(--muted-foreground)]">Loading TCA summary...</div>
      )}

      {!isLoading && !summary && (
        <p className="text-sm text-[var(--muted-foreground)]">No TCA summary available.</p>
      )}

      {summary && (
        <>
          {/* Top-level stats */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">Total Orders</p>
              <p className="mt-1 font-mono text-lg font-semibold">{summary.total_orders}</p>
            </div>
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">Avg Total Cost</p>
              <p className="mt-1 font-mono text-lg font-semibold">
                {fmtBps(summary.avg_total_cost_bps)}{" "}
                <span className="text-xs font-normal text-[var(--muted-foreground)]">bps</span>
              </p>
            </div>
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">Total Cost</p>
              <p className="mt-1 font-mono text-lg font-semibold">
                {fmtCurrency(summary.total_cost_usd)}
              </p>
            </div>
          </div>

          {/* Cost breakdown bar */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
            <p className="mb-3 text-xs font-medium text-[var(--muted-foreground)]">
              Average Cost Breakdown (bps)
            </p>
            <CostBar summary={summary} />
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <Legend color="#6366f1" label="Commission" value={fmtBps(summary.avg_commission_bps)} />
              <Legend color="#f59e0b" label="Spread" value={fmtBps(summary.avg_spread_cost_bps)} />
              <Legend color="#ef4444" label="Timing" value={fmtBps(summary.avg_timing_cost_bps)} />
              <Legend color="#8b5cf6" label="Impact" value={fmtBps(summary.avg_impact_cost_bps)} />
            </div>
          </div>

          {/* Period info */}
          <p className="text-xs text-[var(--muted-foreground)]">
            Period: {new Date(summary.period_start).toLocaleDateString()} &ndash;{" "}
            {new Date(summary.period_end).toLocaleDateString()}
          </p>
        </>
      )}
    </div>
  );
}

function CostBar({
  summary,
}: {
  summary: {
    avg_commission_bps: string;
    avg_spread_cost_bps: string;
    avg_timing_cost_bps: string;
    avg_impact_cost_bps: string;
  };
}) {
  const segments = [
    { value: parseFloat(summary.avg_commission_bps), color: "#6366f1" },
    { value: parseFloat(summary.avg_spread_cost_bps), color: "#f59e0b" },
    { value: parseFloat(summary.avg_timing_cost_bps), color: "#ef4444" },
    { value: parseFloat(summary.avg_impact_cost_bps), color: "#8b5cf6" },
  ];

  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) {
    return (
      <div className="h-5 w-full rounded bg-[var(--border)]" />
    );
  }

  return (
    <div className="flex h-5 w-full overflow-hidden rounded">
      {segments.map((seg, i) => {
        const pct = (seg.value / total) * 100;
        if (pct <= 0) return null;
        return (
          <div
            key={i}
            style={{
              width: `${pct}%`,
              backgroundColor: seg.color,
            }}
            className="h-full"
          />
        );
      })}
    </div>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-[var(--muted-foreground)]">{label}:</span>
      <span className="font-mono font-medium">{value}</span>
    </span>
  );
}
