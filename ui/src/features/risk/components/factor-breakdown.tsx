"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { factorDecompositionQueryOptions } from "../api";

export function FactorBreakdown({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(factorDecompositionQueryOptions(fundSlug, portfolioId));

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">Loading factor decomposition...</div>
    );
  }

  if (!data) {
    return <p className="text-sm text-[var(--muted-foreground)]">No factor data available.</p>;
  }

  const systematicPct = parseFloat(data.systematic_pct);
  const idiosyncraticPct = 100 - systematicPct;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-[var(--border)] p-4">
        <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">
          Systematic vs Idiosyncratic Variance
        </p>
        <div className="flex h-4 overflow-hidden rounded-full">
          <div
            className="bg-[var(--primary)] transition-all"
            style={{ width: `${systematicPct}%` }}
          />
          <div
            className="bg-[var(--border-bright)] transition-all"
            style={{ width: `${idiosyncraticPct}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between text-xs text-[var(--muted-foreground)]">
          <span>Systematic: {systematicPct.toFixed(1)}%</span>
          <span>Idiosyncratic: {idiosyncraticPct.toFixed(1)}%</span>
        </div>
      </div>

      {data.factor_exposures.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
                <th className="px-4 py-2 text-left font-medium text-[var(--muted-foreground)]">
                  Factor
                </th>
                <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                  Exposure
                </th>
                <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                  Contribution
                </th>
                <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                  % of Total
                </th>
              </tr>
            </thead>
            <tbody>
              {data.factor_exposures.map((f) => (
                <tr
                  key={f.factor}
                  className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-4 py-2 font-medium">{f.factor}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {parseFloat(f.exposure).toFixed(4)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {parseFloat(f.contribution).toFixed(4)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {parseFloat(f.pct_of_total).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
