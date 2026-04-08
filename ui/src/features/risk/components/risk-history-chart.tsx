"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { riskHistoryQueryOptions } from "@/features/risk/api";
import { LineChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const fmtCurrency = (v: number) =>
  Math.abs(v) >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M` : `$${(v / 1_000).toFixed(0)}K`;

/** Hook to check if risk history has enough data for a chart. */
export function useHasRiskHistory(portfolioId: string): boolean {
  const { fundSlug } = useFundContext();
  const { data } = useQuery(riskHistoryQueryOptions(fundSlug, portfolioId));
  return !!data && data.length >= 2;
}

export function RiskHistoryChart({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(riskHistoryQueryOptions(fundSlug, portfolioId));

  const series = useMemo(() => {
    if (!data || data.length < 2) return [];
    const sorted = [...data].sort(
      (a, b) => new Date(a.snapshot_at).getTime() - new Date(b.snapshot_at).getTime(),
    );
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
  }, [data]);

  // Latest values for the summary strip
  const latest =
    data && data.length > 0
      ? [...data].sort(
          (a, b) => new Date(b.snapshot_at).getTime() - new Date(a.snapshot_at).getTime(),
        )[0]
      : null;

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>;
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

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      {/* Latest values strip */}
      {latest && (
        <div className="mb-3 flex items-center gap-3 text-xs">
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

      <LineChart
        series={series}
        height={220}
        showXLabels
        xLabelInterval={Math.max(1, Math.floor(series[0].data.length / 8))}
        formatY={fmtCurrency}
      />
    </div>
  );
}
