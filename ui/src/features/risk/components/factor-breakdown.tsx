"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { DivergingHBarChart, HBarChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { factorDecompositionQueryOptions } from "../api";

export function FactorBreakdown({
  portfolioId,
  fullWidth,
}: {
  portfolioId: string;
  fullWidth?: boolean;
}) {
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

  const exposureItems = useMemo(() => {
    if (!data) return [];
    return data.factor_exposures
      .map((f) => ({
        label: f.factor_name,
        value: parseFloat(f.exposure_value),
      }))
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  }, [data]);

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">Loading factor decomposition...</div>
    );
  }

  if (!data?.factor_exposures) return null;

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

  const exposureChart =
    exposureItems.length > 0 ? (
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Factor Exposure
        </p>
        <DivergingHBarChart
          items={exposureItems}
          formatValue={(v) => v.toFixed(3)}
        />
      </div>
    ) : null;

  const factorChart =
    chartItems.length > 0 ? (
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Factor Risk Contribution (% of Total)
        </p>
        <HBarChart items={chartItems} formatValue={(v) => `${v.toFixed(1)}%`} />
      </div>
    ) : null;

  const factorTable =
    data.factor_exposures.length > 0 ? (
      <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
        <table className="min-w-full divide-y divide-[var(--border)] text-sm">
          <thead>
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                Factor
              </th>
              <th scope="col" className="px-3 py-2 text-right font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                Exposure
              </th>
              <th scope="col" className="px-3 py-2 text-right font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                Beta
              </th>
              <th scope="col" className="px-3 py-2 text-right font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                % of Total
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {data.factor_exposures.map((f) => (
              <tr
                key={f.factor}
                className="transition-colors hover:bg-[var(--table-row-hover)]"
              >
                <td className="px-3 py-1.5 font-medium">{f.factor}</td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {parseFloat(f.exposure_value).toFixed(4)}
                </td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {parseFloat(f.beta).toFixed(4)}
                </td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {parseFloat(f.pct_of_total).toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : null;

  if (fullWidth) {
    return (
      <div className="space-y-2">
        <div className="grid grid-cols-3 gap-2">
          <div>{systematicBar}</div>
          <div>{factorChart}</div>
          <div>{exposureChart}</div>
        </div>
        {factorTable}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {systematicBar}
      {exposureChart}
      {factorChart}
      {factorTable}
    </div>
  );
}
