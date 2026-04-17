"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { LoadingSkeleton } from "@mini-hedge/ui";
import { riskHistoryQueryOptions } from "@/features/risk/api";
import type { RiskSnapshot } from "@/features/risk/types";
import { LineChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const fmtCurrency = (v: number) =>
  Math.abs(v) >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M` : `$${(v / 1_000).toFixed(0)}K`;

const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;

type ComparisonPeriod = "none" | "30d" | "90d" | "180d";

const COMPARISON_OPTIONS: { value: ComparisonPeriod; label: string }[] = [
  { value: "none", label: "None" },
  { value: "30d", label: "30d ago" },
  { value: "90d", label: "90d ago" },
  { value: "180d", label: "180d ago" },
];

const PERIOD_DAYS: Record<ComparisonPeriod, number> = {
  none: 0,
  "30d": 30,
  "90d": 90,
  "180d": 180,
};

/** Hook to check if risk history has enough data for a chart. */
export function useHasRiskHistory(portfolioId: string): boolean {
  const { fundSlug } = useFundContext();
  const { data } = useQuery(riskHistoryQueryOptions(fundSlug, portfolioId));
  return !!data && data.length >= 2;
}

/**
 * Given a sorted array of snapshots, find the snapshot closest to a target date.
 */
function findClosestSnapshot(
  sorted: RiskSnapshot[],
  targetDate: Date,
): RiskSnapshot | null {
  if (sorted.length === 0) return null;
  let closest = sorted[0];
  let minDiff = Math.abs(new Date(closest.snapshot_at).getTime() - targetDate.getTime());
  for (const snap of sorted) {
    const diff = Math.abs(new Date(snap.snapshot_at).getTime() - targetDate.getTime());
    if (diff < minDiff) {
      minDiff = diff;
      closest = snap;
    }
  }
  return closest;
}

interface ComparisonMetric {
  label: string;
  current: number;
  comparison: number;
  format: (v: number) => string;
  /** true when a higher absolute value is worse */
  higherIsWorse?: boolean;
}

function ComparisonTable({
  metrics,
  periodLabel,
}: {
  metrics: ComparisonMetric[];
  periodLabel: string;
}) {
  return (
    <div className="mt-3 rounded-md border border-[var(--border)] bg-[var(--card)]">
      <div className="border-b border-[var(--border)] px-3 py-1.5">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Current vs {periodLabel}
        </p>
      </div>
      <div className="grid grid-cols-4 gap-px text-xs">
        {/* Header row */}
        <div className="px-3 py-1.5 font-medium text-[var(--muted-foreground)]">Metric</div>
        <div className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">Now</div>
        <div className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
          {periodLabel}
        </div>
        <div className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
          Change
        </div>

        {metrics.map((m) => {
          const delta = m.current - m.comparison;
          const deltaPct = m.comparison !== 0 ? delta / Math.abs(m.comparison) : 0;
          const isWorse = m.higherIsWorse ? delta > 0 : delta < 0;
          const changeColor =
            Math.abs(deltaPct) < 0.01
              ? "var(--muted-foreground)"
              : isWorse
                ? "var(--destructive)"
                : "var(--success)";

          return (
            <div key={m.label} className="contents">
              <div className="px-3 py-1 text-[var(--foreground)]">{m.label}</div>
              <div className="px-3 py-1 text-right font-mono">{m.format(m.current)}</div>
              <div className="px-3 py-1 text-right font-mono text-[var(--muted-foreground)]">
                {m.format(m.comparison)}
              </div>
              <div className="px-3 py-1 text-right font-mono" style={{ color: changeColor }}>
                {delta >= 0 ? "+" : ""}
                {(deltaPct * 100).toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RiskHistoryChart({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(riskHistoryQueryOptions(fundSlug, portfolioId));
  const [comparison, setComparison] = useState<ComparisonPeriod>("none");

  const sorted = useMemo(() => {
    if (!data || data.length < 2) return [];
    return [...data].sort(
      (a, b) => new Date(a.snapshot_at).getTime() - new Date(b.snapshot_at).getTime(),
    );
  }, [data]);

  const series = useMemo(() => {
    if (sorted.length < 2) return [];
    return [
      {
        label: "VaR 95%",
        color: "var(--warning)",
        data: sorted.map((s) => ({
          x: new Date(s.snapshot_at).toISOString().slice(0, 10),
          y: Math.abs(Number(s.var_95_1d)),
        })),
      },
      {
        label: "VaR 99%",
        color: "var(--destructive)",
        data: sorted.map((s) => ({
          x: new Date(s.snapshot_at).toISOString().slice(0, 10),
          y: Math.abs(Number(s.var_99_1d)),
        })),
      },
      {
        label: "ES 95%",
        color: "var(--primary)",
        dashed: true,
        data: sorted.map((s) => ({
          x: new Date(s.snapshot_at).toISOString().slice(0, 10),
          y: Math.abs(Number(s.expected_shortfall_95)),
        })),
      },
    ];
  }, [sorted]);

  // Build comparison overlay series by shifting historical data forward in time
  const comparisonSeries = useMemo(() => {
    if (comparison === "none" || sorted.length < 2) return [];

    const offsetDays = PERIOD_DAYS[comparison];
    const offsetMs = offsetDays * 24 * 60 * 60 * 1000;

    // Shift each snapshot forward by offsetDays so it aligns with the current period
    const shifted = sorted.map((s) => ({
      ...s,
      _shiftedDate: new Date(new Date(s.snapshot_at).getTime() + offsetMs),
    }));

    // Only include snapshots whose shifted date falls within the current data range
    const currentStart = new Date(sorted[0].snapshot_at).getTime();
    const currentEnd = new Date(sorted[sorted.length - 1].snapshot_at).getTime();
    const inRange = shifted.filter((s) => {
      const t = s._shiftedDate.getTime();
      return t >= currentStart && t <= currentEnd;
    });

    if (inRange.length < 2) return [];

    return [
      {
        label: `VaR 95% (${COMPARISON_OPTIONS.find((o) => o.value === comparison)?.label})`,
        color: "var(--warning)",
        dashed: true,
        data: inRange.map((s) => ({
          x: s._shiftedDate.toISOString().slice(0, 10),
          y: Math.abs(Number(s.var_95_1d)),
        })),
      },
      {
        label: `VaR 99% (${COMPARISON_OPTIONS.find((o) => o.value === comparison)?.label})`,
        color: "var(--destructive)",
        dashed: true,
        data: inRange.map((s) => ({
          x: s._shiftedDate.toISOString().slice(0, 10),
          y: Math.abs(Number(s.var_99_1d)),
        })),
      },
    ];
  }, [comparison, sorted]);

  // Comparison metrics table data
  const comparisonMetrics = useMemo((): ComparisonMetric[] | null => {
    if (comparison === "none" || sorted.length < 2) return null;

    const latestSnapshot = sorted[sorted.length - 1];
    const latestDate = new Date(latestSnapshot.snapshot_at);
    const offsetDays = PERIOD_DAYS[comparison];
    const targetDate = new Date(latestDate.getTime() - offsetDays * 24 * 60 * 60 * 1000);
    const comparisonSnapshot = findClosestSnapshot(sorted, targetDate);

    if (!comparisonSnapshot) return null;

    // Ensure the comparison snapshot is actually far enough in the past (at least half the offset)
    const actualDaysDiff =
      (latestDate.getTime() - new Date(comparisonSnapshot.snapshot_at).getTime()) /
      (24 * 60 * 60 * 1000);
    if (actualDaysDiff < offsetDays * 0.25) return null;

    return [
      {
        label: "VaR 95%",
        current: Math.abs(Number(latestSnapshot.var_95_1d)),
        comparison: Math.abs(Number(comparisonSnapshot.var_95_1d)),
        format: fmtCurrency,
        higherIsWorse: true,
      },
      {
        label: "VaR 99%",
        current: Math.abs(Number(latestSnapshot.var_99_1d)),
        comparison: Math.abs(Number(comparisonSnapshot.var_99_1d)),
        format: fmtCurrency,
        higherIsWorse: true,
      },
      {
        label: "ES 95%",
        current: Math.abs(Number(latestSnapshot.expected_shortfall_95)),
        comparison: Math.abs(Number(comparisonSnapshot.expected_shortfall_95)),
        format: fmtCurrency,
        higherIsWorse: true,
      },
      {
        label: "Max Drawdown",
        current: Math.abs(Number(latestSnapshot.max_drawdown)),
        comparison: Math.abs(Number(comparisonSnapshot.max_drawdown)),
        format: fmtPct,
        higherIsWorse: true,
      },
      ...(latestSnapshot.sharpe_ratio != null && comparisonSnapshot.sharpe_ratio != null
        ? [
            {
              label: "Sharpe",
              current: Number(latestSnapshot.sharpe_ratio),
              comparison: Number(comparisonSnapshot.sharpe_ratio),
              format: (v: number) => v.toFixed(2),
              higherIsWorse: false,
            },
          ]
        : []),
    ];
  }, [comparison, sorted]);

  // Latest values for the summary strip
  const latest =
    data && data.length > 0
      ? [...data].sort(
          (a, b) => new Date(b.snapshot_at).getTime() - new Date(a.snapshot_at).getTime(),
        )[0]
      : null;

  if (isLoading) {
    return <LoadingSkeleton height="18rem" />;
  }

  if (!data || data.length < 2) {
    return (
      <div className="flex items-center justify-center rounded-md border border-dashed border-[var(--border)] p-6">
        <p className="text-xs text-[var(--muted-foreground)]">
          {data?.length === 1
            ? "1 snapshot — chart needs 2+"
            : "Take snapshots to build risk history"}
        </p>
      </div>
    );
  }

  const allSeries = [...series, ...comparisonSeries];
  const periodLabel =
    COMPARISON_OPTIONS.find((o) => o.value === comparison)?.label ?? "";

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      {/* Header: latest values + comparison controls */}
      <div className="mb-3 flex items-center justify-between">
        {/* Latest values strip */}
        {latest && (
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-4 rounded-sm"
                style={{ backgroundColor: "var(--warning)" }}
              />
              <span className="text-[var(--muted-foreground)]">VaR 95%:</span>
              <span className="font-mono font-semibold">
                {fmtCurrency(Math.abs(Number(latest.var_95_1d)))}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-4 rounded-sm"
                style={{ backgroundColor: "var(--destructive)" }}
              />
              <span className="text-[var(--muted-foreground)]">VaR 99%:</span>
              <span className="font-mono font-semibold">
                {fmtCurrency(Math.abs(Number(latest.var_99_1d)))}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-4 rounded-sm border border-dashed border-[var(--primary)]" />
              <span className="text-[var(--muted-foreground)]">ES 95%:</span>
              <span className="font-mono font-semibold">
                {fmtCurrency(Math.abs(Number(latest.expected_shortfall_95)))}
              </span>
            </div>
          </div>
        )}

        {/* Comparison period selector */}
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-[var(--muted-foreground)]">Compare:</span>
          <div className="flex rounded-md border border-[var(--border)] bg-[var(--card)]">
            {COMPARISON_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setComparison(opt.value)}
                className={`px-2 py-0.5 text-[11px] transition-colors first:rounded-l-md last:rounded-r-md ${
                  comparison === opt.value
                    ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <LineChart
        series={allSeries}
        height={220}
        showXLabels
        xLabelInterval={Math.max(1, Math.floor(series[0].data.length / 8))}
        formatY={fmtCurrency}
      />

      {/* Comparison metrics table */}
      {comparison !== "none" && comparisonMetrics && comparisonMetrics.length > 0 && (
        <ComparisonTable metrics={comparisonMetrics} periodLabel={periodLabel} />
      )}

      {comparison !== "none" && !comparisonMetrics && (
        <p className="mt-2 text-center text-[11px] text-[var(--muted-foreground)]">
          Not enough history to compare with {periodLabel}
        </p>
      )}
    </div>
  );
}
