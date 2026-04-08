"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { WaterfallChart } from "@/shared/components/charts";
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

  const waterfallItems = useMemo(() => {
    if (!data) return [];
    return [
      { label: "Allocation", value: parseFloat(data.total_allocation) },
      { label: "Selection", value: parseFloat(data.total_selection) },
      { label: "Interaction", value: parseFloat(data.total_interaction) },
      { label: "Active", value: parseFloat(data.active_return), isTotal: true },
    ];
  }, [data]);

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading attribution...</div>;
  }

  if (!data?.sectors) return null;

  return (
    <div className="space-y-2">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-2">
        <SummaryCard label="Portfolio Return" value={pct(data.portfolio_return)} />
        <SummaryCard label="Benchmark Return" value={pct(data.benchmark_return)} />
        <SummaryCard
          label="Active Return"
          value={pct(data.active_return)}
          highlight={parseFloat(data.active_return) > 0 ? "success" : "destructive"}
        />
      </div>

      {/* Waterfall chart */}
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Attribution Decomposition
        </p>
        <WaterfallChart
          items={waterfallItems}
          height={180}
          formatValue={(v) => `${(v * 100).toFixed(2)}%`}
        />
      </div>

      {/* Contribution cards */}
      <div className="grid grid-cols-3 gap-2">
        <SummaryCard label="Total Allocation" value={pct(data.total_allocation)} />
        <SummaryCard label="Total Selection" value={pct(data.total_selection)} />
        <SummaryCard label="Total Interaction" value={pct(data.total_interaction)} />
      </div>

      {/* Sector detail table */}
      <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="px-3 py-1 font-medium">Sector</th>
              <th className="px-3 py-1 font-medium text-right">Port Weight</th>
              <th className="px-3 py-1 font-medium text-right">Bench Weight</th>
              <th className="px-3 py-1 font-medium text-right">Port Return</th>
              <th className="px-3 py-1 font-medium text-right">Bench Return</th>
              <th className="px-3 py-1 font-medium text-right">Allocation</th>
              <th className="px-3 py-1 font-medium text-right">Selection</th>
              <th className="px-3 py-1 font-medium text-right">Interaction</th>
              <th className="px-3 py-1 font-medium text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.sectors.map((s) => {
              const totalEffect = parseFloat(s.total_effect);
              return (
                <tr key={s.sector} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-3 py-1 font-medium">{s.sector}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(s.portfolio_weight)}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(s.benchmark_weight)}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(s.portfolio_return)}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(s.benchmark_return)}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(s.allocation_effect)}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(s.selection_effect)}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(s.interaction_effect)}</td>
                  <td
                    className="px-3 py-2 text-right font-mono font-semibold"
                    style={{
                      color:
                        totalEffect > 0
                          ? "var(--success)"
                          : totalEffect < 0
                            ? "var(--destructive)"
                            : undefined,
                    }}
                  >
                    {pct(s.total_effect)}
                  </td>
                </tr>
              );
            })}
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

function SummaryCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: "success" | "destructive";
}) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p
        className="mt-0.5 font-mono text-sm font-semibold"
        style={highlight ? { color: `var(--${highlight})` } : undefined}
      >
        {value}
      </p>
    </div>
  );
}
