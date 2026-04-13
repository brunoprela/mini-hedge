"use client";

import { useQuery } from "@tanstack/react-query";
import type { BrokerScorecard } from "@mini-hedge/api-types";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { brokerScorecardsQueryOptions } from "../api";

/** Aggregate scorecards by broker_id (collapses instrument_class rows). */
function aggregateByBroker(scorecards: BrokerScorecard[]): AggregatedBroker[] {
  const map = new Map<
    string,
    {
      totalOrders: number;
      totalFills: number;
      totalRejects: number;
      slippageSum: number;
      costSum: number;
      fillTimeSum: number;
      fillRateSum: number;
      count: number;
    }
  >();

  for (const sc of scorecards) {
    const existing = map.get(sc.broker_id);
    if (existing) {
      existing.totalOrders += sc.total_orders;
      existing.totalFills += sc.total_fills;
      existing.totalRejects += sc.total_rejects;
      existing.slippageSum += parseFloat(sc.avg_slippage_bps) * sc.total_orders;
      existing.costSum += parseFloat(sc.avg_cost_bps) * sc.total_orders;
      existing.fillTimeSum += sc.avg_fill_time_ms * sc.total_orders;
      existing.fillRateSum += parseFloat(sc.fill_rate) * sc.total_orders;
      existing.count += sc.total_orders;
    } else {
      map.set(sc.broker_id, {
        totalOrders: sc.total_orders,
        totalFills: sc.total_fills,
        totalRejects: sc.total_rejects,
        slippageSum: parseFloat(sc.avg_slippage_bps) * sc.total_orders,
        costSum: parseFloat(sc.avg_cost_bps) * sc.total_orders,
        fillTimeSum: sc.avg_fill_time_ms * sc.total_orders,
        fillRateSum: parseFloat(sc.fill_rate) * sc.total_orders,
        count: sc.total_orders,
      });
    }
  }

  return Array.from(map.entries())
    .map(([brokerId, d]) => ({
      brokerId,
      totalOrders: d.totalOrders,
      totalFills: d.totalFills,
      totalRejects: d.totalRejects,
      avgSlippageBps: d.count > 0 ? d.slippageSum / d.count : 0,
      avgCostBps: d.count > 0 ? d.costSum / d.count : 0,
      avgFillTimeMs: d.count > 0 ? d.fillTimeSum / d.count : 0,
      fillRate: d.count > 0 ? d.fillRateSum / d.count : 0,
    }))
    .sort((a, b) => b.totalOrders - a.totalOrders);
}

interface AggregatedBroker {
  brokerId: string;
  totalOrders: number;
  totalFills: number;
  totalRejects: number;
  avgSlippageBps: number;
  avgCostBps: number;
  avgFillTimeMs: number;
  fillRate: number;
}

// --- Metric helpers ---

interface MetricDef {
  label: string;
  key: keyof AggregatedBroker;
  format: (v: number) => string;
  /** "lower" means a lower value is better, "higher" means higher is better. */
  direction: "lower" | "higher";
}

const METRICS: MetricDef[] = [
  {
    label: "Total Orders",
    key: "totalOrders",
    format: (v) => v.toLocaleString(),
    direction: "higher",
  },
  {
    label: "Fill Rate",
    key: "fillRate",
    format: (v) => `${(v * 100).toFixed(1)}%`,
    direction: "higher",
  },
  {
    label: "Avg Slippage",
    key: "avgSlippageBps",
    format: (v) => `${v.toFixed(2)} bps`,
    direction: "lower",
  },
  {
    label: "Avg Cost",
    key: "avgCostBps",
    format: (v) => `${v.toFixed(2)} bps`,
    direction: "lower",
  },
  {
    label: "Avg Latency",
    key: "avgFillTimeMs",
    format: (v) => `${Math.round(v)} ms`,
    direction: "lower",
  },
  {
    label: "Rejects",
    key: "totalRejects",
    format: (v) => v.toLocaleString(),
    direction: "lower",
  },
];

function metricColor(
  value: number,
  allValues: number[],
  direction: "lower" | "higher",
): string {
  if (allValues.length <= 1) return "var(--foreground)";
  const best = direction === "lower" ? Math.min(...allValues) : Math.max(...allValues);
  const worst = direction === "lower" ? Math.max(...allValues) : Math.min(...allValues);
  if (value === best) return "var(--success)";
  if (value === worst && best !== worst) return "var(--destructive)";
  return "var(--foreground)";
}

/** Max value across brokers for a given metric (for the bar chart). */
function maxForMetric(brokers: AggregatedBroker[], key: keyof AggregatedBroker): number {
  return Math.max(...brokers.map((b) => Number(b[key])), 1);
}

// --- Bar colors per broker (cycled) ---
const BAR_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4"];

export function BrokerScorecardComparison() {
  const { fundSlug } = useFundContext();
  const { data: scorecards, isLoading } = useQuery(brokerScorecardsQueryOptions(fundSlug));

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">Loading broker scorecards...</div>
    );
  }

  if (!scorecards || scorecards.length === 0) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">
        No broker scorecard data available.
      </div>
    );
  }

  const brokers = aggregateByBroker(scorecards);

  return (
    <div className="space-y-4">
      {/* Comparison table */}
      <div className="overflow-x-auto rounded-md border border-[var(--border)]">
        <table className="min-w-full divide-y divide-[var(--border)] text-sm">
          <thead>
            <tr className="text-left text-xs text-[var(--muted-foreground)]">
              <th scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">Metric</th>
              {brokers.map((b) => (
                <th scope="col" key={b.brokerId} className="whitespace-nowrap px-3 py-2 text-right font-mono font-semibold">
                  {b.brokerId}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {METRICS.map((m) => {
              const allValues = brokers.map((b) => Number(b[m.key]));
              return (
                <tr
                  key={m.key}
                  className="hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">{m.label}</td>
                  {brokers.map((b) => {
                    const v = Number(b[m.key]);
                    return (
                      <td
                        key={b.brokerId}
                        className="px-3 py-2 text-right font-mono font-medium"
                        style={{ color: metricColor(v, allValues, m.direction) }}
                      >
                        {m.format(v)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Simple bar chart comparing key metrics */}
      <div className="grid gap-3 sm:grid-cols-2">
        <BarChart
          title="Avg Slippage (bps)"
          brokers={brokers}
          metricKey="avgSlippageBps"
          format={(v) => v.toFixed(2)}
        />
        <BarChart
          title="Fill Rate (%)"
          brokers={brokers}
          metricKey="fillRate"
          format={(v) => (v * 100).toFixed(1)}
          transform={(v) => v * 100}
        />
        <BarChart
          title="Avg Cost (bps)"
          brokers={brokers}
          metricKey="avgCostBps"
          format={(v) => v.toFixed(2)}
        />
        <BarChart
          title="Avg Latency (ms)"
          brokers={brokers}
          metricKey="avgFillTimeMs"
          format={(v) => Math.round(v).toString()}
        />
      </div>
    </div>
  );
}

function BarChart({
  title,
  brokers,
  metricKey,
  format,
  transform,
}: {
  title: string;
  brokers: AggregatedBroker[];
  metricKey: keyof AggregatedBroker;
  format: (v: number) => string;
  transform?: (v: number) => number;
}) {
  const max = maxForMetric(
    brokers,
    metricKey,
  );
  const transformedMax = transform ? transform(max) : max;
  const effectiveMax = transformedMax > 0 ? transformedMax : 1;

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">{title}</p>
      <div className="space-y-1.5">
        {brokers.map((b, i) => {
          const raw = Number(b[metricKey]);
          const value = transform ? transform(raw) : raw;
          const pct = Math.max((value / effectiveMax) * 100, 2);
          return (
            <div key={b.brokerId} className="flex items-center gap-2">
              <span className="w-20 shrink-0 truncate text-right font-mono text-xs text-[var(--muted-foreground)]">
                {b.brokerId}
              </span>
              <div className="flex-1">
                <div
                  className="h-4 rounded-sm"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
                  }}
                />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-xs">{format(raw)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
