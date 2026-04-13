"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { WaterfallChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { stressTestsQueryOptions } from "../api";

function fmtCurrency(v: number) {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function StressWaterfallChart({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: results, isLoading } = useQuery(stressTestsQueryOptions(fundSlug, portfolioId));
  const [selectedIndex, setSelectedIndex] = useState(0);

  if (isLoading) {
    return <div className="text-xs text-[var(--muted-foreground)]">Loading...</div>;
  }

  if (!results || results.length === 0) return null;

  // Find the scenario with position impacts for best visualization
  const scenariosWithImpacts = results.filter((r) => r.position_impacts.length > 0);
  const displayResults = scenariosWithImpacts.length > 0 ? scenariosWithImpacts : results;
  const selected = displayResults[Math.min(selectedIndex, displayResults.length - 1)];

  // Build waterfall items from position impacts
  const hasPositionImpacts = selected.position_impacts.length > 0;

  const waterfallItems = hasPositionImpacts
    ? buildPositionWaterfall(selected)
    : buildScenarioOverview(results);

  return (
    <div className="space-y-2 rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
          Stress Waterfall
        </h4>
        {hasPositionImpacts && displayResults.length > 1 && (
          <select
            value={selectedIndex}
            onChange={(e) => setSelectedIndex(Number(e.target.value))}
            className="rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-xs outline-none focus:border-[var(--ring)]"
          >
            {displayResults.map((r, i) => (
              <option key={r.scenario_name} value={i}>
                {r.scenario_name}
              </option>
            ))}
          </select>
        )}
      </div>

      <WaterfallChart
        items={waterfallItems}
        height={220}
        formatValue={fmtCurrency}
      />
    </div>
  );
}

/**
 * Build waterfall from a single scenario's position impacts.
 * Start bar = sum of current values, each bar = position PnL impact, final bar = stressed total.
 */
function buildPositionWaterfall(
  result: { position_impacts: { instrument_id: string; current_value: string; pnl_impact: string; stressed_value: string }[]; total_pnl_impact: string },
) {
  const impacts = result.position_impacts;

  // Starting portfolio value = sum of current values
  const startingValue = impacts.reduce((acc, p) => acc + parseFloat(p.current_value), 0);

  // Sort by absolute impact descending for visual clarity
  const sorted = [...impacts].sort(
    (a, b) => Math.abs(parseFloat(b.pnl_impact)) - Math.abs(parseFloat(a.pnl_impact)),
  );

  const items: { label: string; value: number; isTotal?: boolean }[] = [
    { label: "Current", value: startingValue, isTotal: true },
  ];

  for (const impact of sorted) {
    items.push({
      label: impact.instrument_id.length > 8
        ? impact.instrument_id.slice(0, 8)
        : impact.instrument_id,
      value: parseFloat(impact.pnl_impact),
    });
  }

  items.push({
    label: "Stressed",
    value: startingValue + parseFloat(result.total_pnl_impact),
    isTotal: true,
  });

  return items;
}

/**
 * Build a cross-scenario waterfall showing cumulative worst-case impacts.
 * Each bar is the total PnL impact of a scenario (not cumulative, standalone).
 */
function buildScenarioOverview(
  results: { scenario_name: string; total_pnl_impact: string }[],
) {
  // Sort by impact (most negative first)
  const sorted = [...results].sort(
    (a, b) => parseFloat(a.total_pnl_impact) - parseFloat(b.total_pnl_impact),
  );

  return sorted.map((r) => ({
    label: r.scenario_name.length > 10 ? r.scenario_name.slice(0, 10) : r.scenario_name,
    value: parseFloat(r.total_pnl_impact),
  }));
}
