"use client";

import { WaterfallChart } from "@/shared/components/charts";
import type { TCAReport } from "../types";

interface ImplementationShortfallChartProps {
  report: TCAReport;
}

/**
 * Waterfall chart decomposing implementation shortfall from decision price
 * (arrival) to actual execution price (avg fill).
 *
 * Bars: Decision Price -> +Delay -> +Market Impact -> +Timing -> +Spread -> Execution Price
 *
 * The TCA report provides cost components in bps. We convert the arrival price
 * to a base value and show each component as an incremental cost, ending at
 * the avg fill price.
 */
export function ImplementationShortfallChart({ report }: ImplementationShortfallChartProps) {
  const arrivalPrice = parseFloat(report.arrival_mid_price);
  const avgFillPrice = report.avg_fill_price ? parseFloat(report.avg_fill_price) : arrivalPrice;
  const side = report.side.toLowerCase();

  // Cost components in bps from the TCA report.
  // opportunity_cost_bps acts as the delay cost (cost of waiting to start execution).
  const delayCostBps = parseFloat(report.opportunity_cost_bps);
  const impactCostBps = parseFloat(report.market_impact_cost_bps);
  const timingCostBps = parseFloat(report.timing_cost_bps);
  const spreadCostBps = parseFloat(report.spread_cost_bps);

  // For a sell order, costs are inverted (higher price is favorable).
  const sign = side === "sell" ? -1 : 1;

  // Convert bps to price increments relative to arrival price.
  const bpsToPrice = (bps: number) => (bps / 10000) * arrivalPrice * sign;

  const items = [
    { label: "Decision", value: arrivalPrice, isTotal: true as const },
    { label: "Delay", value: bpsToPrice(delayCostBps) },
    { label: "Impact", value: bpsToPrice(impactCostBps) },
    { label: "Timing", value: bpsToPrice(timingCostBps) },
    { label: "Spread", value: bpsToPrice(spreadCostBps) },
    { label: "Execution", value: avgFillPrice, isTotal: true as const },
  ];

  const fmtPrice = (v: number) => {
    if (Math.abs(v) >= 1) return v.toFixed(2);
    // For small increments show more precision
    return v.toFixed(4);
  };

  const fmtBps = (v: number) => `${v.toFixed(2)} bps`;

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Implementation Shortfall Waterfall
      </p>
      <p className="mb-3 text-xs text-[var(--muted-foreground)]">
        Decomposition from decision price to execution price
      </p>

      <WaterfallChart items={items} height={220} formatValue={fmtPrice} />

      {/* Legend showing bps values */}
      <div className="mt-3 flex flex-wrap gap-3 border-t border-[var(--border)] pt-3">
        {[
          { label: "Delay", bps: delayCostBps },
          { label: "Impact", bps: impactCostBps },
          { label: "Timing", bps: timingCostBps },
          { label: "Spread", bps: spreadCostBps },
        ].map((c) => (
          <div key={c.label} className="flex items-center gap-1.5 text-xs">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{
                backgroundColor:
                  c.bps * sign > 0 ? "var(--destructive)" : c.bps * sign < 0 ? "var(--success)" : "var(--muted-foreground)",
                opacity: 0.8,
              }}
            />
            <span className="text-[var(--muted-foreground)]">{c.label}:</span>
            <span
              className="font-mono font-medium"
              style={{
                color:
                  c.bps > 0 ? "var(--destructive)" : c.bps < 0 ? "var(--success)" : "var(--foreground)",
              }}
            >
              {c.bps > 0 ? "+" : ""}
              {fmtBps(c.bps)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
