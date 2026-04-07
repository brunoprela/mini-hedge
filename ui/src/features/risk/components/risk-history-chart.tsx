"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { riskHistoryQueryOptions } from "@/features/risk/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function RiskHistoryChart({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(riskHistoryQueryOptions(fundSlug, portfolioId));

  const maxVaR = useMemo(() => {
    if (!data || data.length === 0) return 1;
    return Math.max(
      ...data.flatMap((s) => [
        Math.abs(Number(s.var_95_1d)),
        Math.abs(Number(s.var_99_1d)),
      ]),
      1,
    );
  }, [data]);

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>;
  }

  if (!data || data.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No risk history available</p>;
  }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <h3 className="mb-3 text-sm font-medium text-[var(--muted-foreground)]">Historical Risk Snapshots</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="bg-[var(--table-header)] px-3 py-2 font-medium">Date</th>
              <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">VaR 95%</th>
              <th className="bg-[var(--table-header)] px-3 py-2 font-medium" style={{ minWidth: 80 }} />
              <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">VaR 99%</th>
              <th className="bg-[var(--table-header)] px-3 py-2 font-medium" style={{ minWidth: 80 }} />
              <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">ES 95%</th>
              <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">NAV</th>
            </tr>
          </thead>
          <tbody>
            {data.map((snapshot, idx) => {
              const var95 = Math.abs(Number(snapshot.var_95_1d));
              const var99 = Math.abs(Number(snapshot.var_99_1d));
              const es95 = Math.abs(Number(snapshot.expected_shortfall_95));
              const var95Pct = (var95 / maxVaR) * 100;
              const var99Pct = (var99 / maxVaR) * 100;

              const prev95 = idx > 0 ? Math.abs(Number(data[idx - 1].var_95_1d)) : var95;
              const increasing95 = var95 > prev95;
              const prev99 = idx > 0 ? Math.abs(Number(data[idx - 1].var_99_1d)) : var99;
              const increasing99 = var99 > prev99;

              const barColor95 = increasing95 ? "var(--destructive)" : "#f59e0b";
              const barColor99 = increasing99 ? "var(--destructive)" : "#f59e0b";

              const dateStr = new Date(snapshot.snapshot_at).toISOString().slice(0, 10);

              return (
                <tr key={snapshot.id ?? idx} className="border-b border-[var(--table-border)] hover:bg-[var(--table-row-hover)]">
                  <td className="px-3 py-1.5 font-mono text-xs">{dateStr}</td>
                  <td className="px-3 py-1.5 text-right">{fmtCurrency(var95)}</td>
                  <td className="px-3 py-1.5">
                    <div className="h-2.5 w-full rounded bg-[var(--border)]">
                      <div
                        className="h-2.5 rounded"
                        style={{ width: `${var95Pct}%`, backgroundColor: barColor95 }}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-1.5 text-right">{fmtCurrency(var99)}</td>
                  <td className="px-3 py-1.5">
                    <div className="h-2.5 w-full rounded bg-[var(--border)]">
                      <div
                        className="h-2.5 rounded"
                        style={{ width: `${var99Pct}%`, backgroundColor: barColor99 }}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-1.5 text-right">{fmtCurrency(es95)}</td>
                  <td className="px-3 py-1.5 text-right">{fmtCurrency(snapshot.nav)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
