"use client";

import { useState } from "react";
import { DivergingHBarChart } from "@/shared/components/charts";
import type { WhatIfPosition } from "../types";

type ViewMode = "grouped" | "delta";

const SIGNIFICANT_THRESHOLD = 0.02; // 2% weight change

interface WhatIfDiffChartProps {
  positions: WhatIfPosition[];
}

/**
 * Visual diff chart for what-if analysis. Shows before/after weight bars
 * for each position, with an option to toggle to a diverging delta view.
 */
export function WhatIfDiffChart({ positions }: WhatIfDiffChartProps) {
  const [view, setView] = useState<ViewMode>("grouped");

  if (positions.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No position data</p>;
  }

  // Parse weights once and sort by absolute delta descending
  const parsed = positions
    .map((p) => ({
      instrument: p.instrument_id,
      current: parseFloat(p.current_weight),
      proposed: parseFloat(p.proposed_weight),
      delta: parseFloat(p.proposed_weight) - parseFloat(p.current_weight),
    }))
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  const maxWeight = Math.max(...parsed.flatMap((p) => [Math.abs(p.current), Math.abs(p.proposed)]), 0.01);

  const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;

  if (view === "delta") {
    const items = parsed.map((p) => ({
      label: p.instrument,
      value: p.delta,
      color:
        Math.abs(p.delta) >= SIGNIFICANT_THRESHOLD
          ? p.delta >= 0
            ? "var(--success)"
            : "var(--destructive)"
          : undefined,
    }));

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-[var(--muted-foreground)]">
            Weight Change by Instrument
          </p>
          <ViewToggle view={view} onChange={setView} />
        </div>
        <DivergingHBarChart
          items={items}
          formatValue={(v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`}
          positiveColor="var(--primary)"
          negativeColor="var(--destructive)"
        />
      </div>
    );
  }

  // Grouped bar view
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-[var(--muted-foreground)]">
          Portfolio Weights: Current vs Proposed
        </p>
        <ViewToggle view={view} onChange={setView} />
      </div>

      <div className="space-y-1.5">
        {parsed.map((p) => {
          const isSignificant = Math.abs(p.delta) >= SIGNIFICANT_THRESHOLD;
          const currentPct = (Math.abs(p.current) / maxWeight) * 100;
          const proposedPct = (Math.abs(p.proposed) / maxWeight) * 100;

          return (
            <div key={p.instrument} className="flex items-center gap-2 text-xs">
              <span
                className={`w-20 shrink-0 truncate text-right ${isSignificant ? "font-semibold text-[var(--foreground)]" : "text-[var(--muted-foreground)]"}`}
              >
                {p.instrument}
              </span>
              <div className="flex flex-1 flex-col gap-0.5">
                {/* Current bar */}
                <div className="flex items-center gap-1.5">
                  <div
                    className="h-3 rounded-r-sm"
                    style={{
                      width: `${Math.max(currentPct, 0.5)}%`,
                      backgroundColor: "var(--muted-foreground)",
                      opacity: 0.4,
                    }}
                  />
                  <span className="shrink-0 font-mono text-[10px] text-[var(--muted-foreground)]">
                    {fmtPct(p.current)}
                  </span>
                </div>
                {/* Proposed bar */}
                <div className="flex items-center gap-1.5">
                  <div
                    className="h-3 rounded-r-sm"
                    style={{
                      width: `${Math.max(proposedPct, 0.5)}%`,
                      backgroundColor: isSignificant ? "var(--primary)" : "var(--primary)",
                      opacity: isSignificant ? 0.9 : 0.55,
                    }}
                  />
                  <span
                    className="shrink-0 font-mono text-[10px]"
                    style={{
                      color: isSignificant
                        ? p.delta >= 0
                          ? "var(--success)"
                          : "var(--destructive)"
                        : "var(--primary)",
                    }}
                  >
                    {fmtPct(p.proposed)}
                  </span>
                </div>
              </div>
              {/* Delta badge */}
              <span
                className="w-16 shrink-0 text-right font-mono text-[10px]"
                style={{
                  color: isSignificant
                    ? p.delta >= 0
                      ? "var(--success)"
                      : "var(--destructive)"
                    : "var(--muted-foreground)",
                }}
              >
                {p.delta >= 0 ? "+" : ""}
                {(p.delta * 100).toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 pt-1 text-[10px] text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-2 w-4 rounded-sm"
            style={{ backgroundColor: "var(--muted-foreground)", opacity: 0.4 }}
          />
          Current
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-2 w-4 rounded-sm"
            style={{ backgroundColor: "var(--primary)", opacity: 0.75 }}
          />
          Proposed
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: "var(--success)" }}
          />
          Significant change (&ge;2%)
        </span>
      </div>
    </div>
  );
}

function ViewToggle({ view, onChange }: { view: ViewMode; onChange: (v: ViewMode) => void }) {
  return (
    <div className="flex rounded-md border border-[var(--border)] text-[10px]">
      <button
        type="button"
        onClick={() => onChange("grouped")}
        className={`px-2 py-0.5 transition-colors ${
          view === "grouped"
            ? "bg-[var(--foreground)] text-[var(--background)]"
            : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        }`}
      >
        Before / After
      </button>
      <button
        type="button"
        onClick={() => onChange("delta")}
        className={`px-2 py-0.5 transition-colors ${
          view === "delta"
            ? "bg-[var(--foreground)] text-[var(--background)]"
            : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        }`}
      >
        Delta
      </button>
    </div>
  );
}
