"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { HBarChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { factorDecompositionQueryOptions } from "../api";

export function FactorBreakdown({ portfolioId, fullWidth }: { portfolioId: string; fullWidth?: boolean }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(factorDecompositionQueryOptions(fundSlug, portfolioId));

  const chartItems = useMemo(() => {
    if (!data) return [];
    return data.factor_exposures
      .map((f) => ({
        label: f.factor,
        value: parseFloat(f.pct_of_total),
      }))
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  }, [data]);

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">Loading factor decomposition...</div>
    );
  }

  if (!data || !data.factor_exposures) return null;

  const systematicPct = parseFloat(data.systematic_pct);
  const idiosyncraticPct = 100 - systematicPct;

  const systematicBar = (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Systematic vs Idiosyncratic Variance
      </p>
      <div className="flex h-5 overflow-hidden rounded-full">
        <div
          className="flex items-center justify-center bg-[var(--primary)] text-[9px] font-bold text-white transition-all"
          style={{ width: `${systematicPct}%` }}
        >
          {systematicPct > 15 ? `${systematicPct.toFixed(1)}%` : ""}
        </div>
        <div
          className="flex items-center justify-center bg-[var(--border-bright)] text-[9px] font-bold text-[var(--muted-foreground)] transition-all"
          style={{ width: `${idiosyncraticPct}%` }}
        >
          {idiosyncraticPct > 15 ? `${idiosyncraticPct.toFixed(1)}%` : ""}
        </div>
      </div>
      <div className="mt-2 flex justify-between text-xs text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm bg-[var(--primary)]" />
          Systematic
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm bg-[var(--border-bright)]" />
          Idiosyncratic
        </span>
      </div>
    </div>
  );

  const factorChart = chartItems.length > 0 ? (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Factor Risk Contribution (% of Total)
      </p>
      <HBarChart
        items={chartItems}
        formatValue={(v) => `${v.toFixed(1)}%`}
      />
    </div>
  ) : null;

  const factorTable = data.factor_exposures.length > 0 ? (
    <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">Factor</th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">Exposure</th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">Beta</th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">% of Total</th>
          </tr>
        </thead>
        <tbody>
          {data.factor_exposures.map((f) => (
            <tr
              key={f.factor}
              className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
            >
              <td className="px-3 py-1.5 font-medium">{f.factor}</td>
              <td className="px-3 py-1.5 text-right font-mono">{parseFloat(f.exposure_value).toFixed(4)}</td>
              <td className="px-3 py-1.5 text-right font-mono">{parseFloat(f.beta).toFixed(4)}</td>
              <td className="px-3 py-1.5 text-right font-mono">{parseFloat(f.pct_of_total).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : null;

  if (fullWidth) {
    return (
      <div className="grid grid-cols-3 gap-2">
        <div className="space-y-2">
          {systematicBar}
        </div>
        <div>
          {factorChart}
        </div>
        <div>
          {factorTable}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {systematicBar}
      {factorChart}
      {factorTable}
    </div>
  );
}
