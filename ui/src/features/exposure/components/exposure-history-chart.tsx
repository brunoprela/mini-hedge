"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { exposureHistoryQueryOptions } from "@/features/exposure/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const fmt = (v: string) =>
  Number(v).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function toISODate(d: Date) {
  return d.toISOString().slice(0, 10);
}

const RANGE_OPTIONS = [
  { label: "7D", days: 7 },
  { label: "30D", days: 30 },
  { label: "90D", days: 90 },
] as const;

export function ExposureHistoryChart({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const [rangeDays, setRangeDays] = useState(30);

  const { start, end } = useMemo(() => {
    const now = new Date();
    const s = new Date(now);
    s.setDate(s.getDate() - rangeDays);
    return { start: toISODate(s), end: toISODate(now) };
  }, [rangeDays]);

  const { data, isLoading } = useQuery(exposureHistoryQueryOptions(fundSlug, portfolioId, start, end));

  const maxGross = useMemo(() => {
    if (!data || data.length === 0) return 1;
    return Math.max(...data.map((e) => Math.abs(Number(e.gross_value))), 1);
  }, [data]);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--muted-foreground)]">Exposure Over Time</h3>
        <div className="flex gap-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              onClick={() => setRangeDays(opt.days)}
              className={`rounded px-2 py-0.5 text-xs transition-colors ${
                rangeDays === opt.days
                  ? "bg-[var(--foreground)] text-[var(--card)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>}

      {!isLoading && (!data || data.length === 0) && (
        <p className="text-sm text-[var(--muted-foreground)]">No exposure history available</p>
      )}

      {!isLoading && data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--table-border)] text-left text-xs text-[var(--muted-foreground)]">
                <th className="bg-[var(--table-header)] px-3 py-2 font-medium">Date</th>
                <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">Long</th>
                <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">Short</th>
                <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">Net</th>
                <th className="bg-[var(--table-header)] px-3 py-2 font-medium text-right">Gross</th>
                <th className="bg-[var(--table-header)] px-3 py-2 font-medium" style={{ minWidth: 120 }}>
                  Net / Gross
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry) => {
                const net = Number(entry.net_value);
                const gross = Number(entry.gross_value);
                const pct = gross === 0 ? 0 : (net / gross) * 100;
                const barWidth = Math.min(Math.abs(pct), 100);

                return (
                  <tr key={entry.date} className="border-b border-[var(--table-border)] hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-1.5 font-mono text-xs">{entry.date}</td>
                    <td className="px-3 py-1.5 text-right text-[var(--success)]">{fmt(entry.long_value)}</td>
                    <td className="px-3 py-1.5 text-right text-[var(--destructive)]">{fmt(entry.short_value)}</td>
                    <td className="px-3 py-1.5 text-right">{fmt(entry.net_value)}</td>
                    <td className="px-3 py-1.5 text-right">{fmt(entry.gross_value)}</td>
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1">
                        <div className="relative h-3 w-full rounded bg-[var(--border)]">
                          <div
                            className="absolute top-0 h-3 rounded"
                            style={{
                              left: pct >= 0 ? "50%" : `${50 - barWidth / 2}%`,
                              width: `${barWidth / 2}%`,
                              backgroundColor: pct >= 0 ? "var(--success)" : "var(--destructive)",
                            }}
                          />
                          <div
                            className="absolute top-0 h-3 w-px bg-[var(--foreground)]"
                            style={{ left: "50%", opacity: 0.3 }}
                          />
                        </div>
                        <span className="w-10 text-right text-[10px] text-[var(--muted-foreground)]">
                          {pct.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
