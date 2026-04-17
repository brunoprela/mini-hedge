"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { LoadingSkeleton } from "@mini-hedge/ui";
import { exposureHistoryQueryOptions } from "@/features/exposure/api";
import { LineChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const fmt = (v: string) =>
  Number(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

const fmtChartY = (v: number) =>
  Math.abs(v) >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M` : `$${(v / 1_000).toFixed(0)}K`;

/**
 * Default exposure limits (dollar amounts).
 * In production these would come from compliance rules or fund configuration.
 * Set to null to disable a limit line.
 */
const GROSS_EXPOSURE_LIMIT: number | null = 50_000_000; // $50M
const NET_EXPOSURE_UPPER_LIMIT: number | null = 25_000_000; // $25M
const NET_EXPOSURE_LOWER_LIMIT: number | null = -25_000_000; // -$25M

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

  const { data, isLoading } = useQuery(
    exposureHistoryQueryOptions(fundSlug, portfolioId, start, end),
  );

  const sorted = useMemo(() => {
    if (!data || data.length === 0) return [];
    return [...data].sort((a, b) => a.snapshot_at.localeCompare(b.snapshot_at));
  }, [data]);

  const chartSeries = useMemo(() => {
    if (sorted.length < 2) return [];
    return [
      {
        label: "Gross",
        color: "var(--primary)",
        data: sorted.map((e) => ({ x: e.snapshot_at, y: Number(e.gross_exposure) })),
      },
      {
        label: "Net",
        color: "var(--warning)",
        data: sorted.map((e) => ({ x: e.snapshot_at, y: Number(e.net_exposure) })),
      },
      {
        label: "Long",
        color: "var(--success)",
        dashed: true,
        data: sorted.map((e) => ({ x: e.snapshot_at, y: Number(e.long_exposure) })),
      },
      {
        label: "Short",
        color: "var(--destructive)",
        dashed: true,
        data: sorted.map((e) => ({ x: e.snapshot_at, y: Number(e.short_exposure) })),
      },
    ];
  }, [sorted]);

  const limitLines = useMemo(() => {
    const lines: { value: number; label: string; color?: string; dashed?: boolean }[] = [];
    if (GROSS_EXPOSURE_LIMIT != null) {
      lines.push({
        value: GROSS_EXPOSURE_LIMIT,
        label: `Gross Limit ${fmtChartY(GROSS_EXPOSURE_LIMIT)}`,
        color: "var(--destructive)",
      });
    }
    if (NET_EXPOSURE_UPPER_LIMIT != null) {
      lines.push({
        value: NET_EXPOSURE_UPPER_LIMIT,
        label: `Net Limit +${fmtChartY(NET_EXPOSURE_UPPER_LIMIT)}`,
        color: "var(--destructive)",
      });
    }
    if (NET_EXPOSURE_LOWER_LIMIT != null) {
      lines.push({
        value: NET_EXPOSURE_LOWER_LIMIT,
        label: `Net Limit ${fmtChartY(NET_EXPOSURE_LOWER_LIMIT)}`,
        color: "var(--destructive)",
      });
    }
    return lines;
  }, []);

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--muted-foreground)]">Exposure Over Time</h3>
        <div className="flex gap-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              type="button"
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

      {isLoading && <LoadingSkeleton height="15rem" />}

      {/* Line chart with limit overlays */}
      {!isLoading && chartSeries.length > 0 && (
        <div className="mb-4">
          <LineChart
            series={chartSeries}
            height={240}
            showXLabels
            xLabelInterval={Math.max(1, Math.floor(sorted.length / 8))}
            formatY={fmtChartY}
            referenceLines={limitLines}
          />
        </div>
      )}

      {!isLoading && sorted.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border)] text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--muted-foreground)]">
                <th scope="col" className="whitespace-nowrap px-3 py-1 font-semibold">Date</th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 font-semibold text-right">Long</th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 font-semibold text-right">Short</th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 font-semibold text-right">Net</th>
                <th scope="col" className="whitespace-nowrap px-3 py-1 font-semibold text-right">Gross</th>
                <th
                  scope="col"
                  className="whitespace-nowrap px-3 py-1 font-semibold"
                  style={{ minWidth: 120 }}
                >
                  Net / Gross
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {sorted.map((entry) => {
                const net = Number(entry.net_exposure);
                const gross = Number(entry.gross_exposure);
                const pct = gross === 0 ? 0 : (net / gross) * 100;
                const barWidth = Math.min(Math.abs(pct), 100);

                return (
                  <tr
                    key={entry.snapshot_at}
                    className="hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-1.5 font-mono text-xs">{entry.snapshot_at}</td>
                    <td className="px-3 py-1.5 text-right text-[var(--success)]">
                      {fmt(entry.long_exposure)}
                    </td>
                    <td className="px-3 py-1.5 text-right text-[var(--destructive)]">
                      {fmt(entry.short_exposure)}
                    </td>
                    <td className="px-3 py-1.5 text-right">{fmt(entry.net_exposure)}</td>
                    <td className="px-3 py-1.5 text-right">{fmt(entry.gross_exposure)}</td>
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
