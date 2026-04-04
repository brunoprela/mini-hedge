"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { brinsonFachlerQueryOptions } from "../api";

interface Props {
  portfolioId: string;
  start: string;
  end: string;
}

function pct(v: string): string {
  return `${(parseFloat(v) * 100).toFixed(2)}%`;
}

export function BrinsonFachlerTable({ portfolioId, start, end }: Props) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(
    brinsonFachlerQueryOptions(fundSlug, portfolioId, start, end),
  );

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading attribution...</div>;
  }

  if (!data) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">No attribution data available.</div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <SummaryCard label="Portfolio Return" value={pct(data.portfolio_return)} />
        <SummaryCard label="Benchmark Return" value={pct(data.benchmark_return)} />
        <SummaryCard label="Active Return" value={pct(data.active_return)} />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <SummaryCard label="Total Allocation" value={pct(data.total_allocation)} />
        <SummaryCard label="Total Selection" value={pct(data.total_selection)} />
        <SummaryCard label="Total Interaction" value={pct(data.total_interaction)} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="px-3 py-2 font-medium">Sector</th>
              <th className="px-3 py-2 font-medium text-right">Port Weight</th>
              <th className="px-3 py-2 font-medium text-right">Bench Weight</th>
              <th className="px-3 py-2 font-medium text-right">Port Return</th>
              <th className="px-3 py-2 font-medium text-right">Bench Return</th>
              <th className="px-3 py-2 font-medium text-right">Allocation</th>
              <th className="px-3 py-2 font-medium text-right">Selection</th>
              <th className="px-3 py-2 font-medium text-right">Interaction</th>
              <th className="px-3 py-2 font-medium text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.sectors.map((s) => (
              <tr key={s.sector} className="border-b border-[var(--border)] last:border-0">
                <td className="px-3 py-2">{s.sector}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.portfolio_weight)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.benchmark_weight)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.portfolio_return)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.benchmark_return)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.allocation_effect)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.selection_effect)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.interaction_effect)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(s.total_effect)}</td>
              </tr>
            ))}
            {data.sectors.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-4 text-center text-[var(--muted-foreground)]">
                  No sector data for this period.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}
