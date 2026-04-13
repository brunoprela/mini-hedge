"use client";

import { useMemo } from "react";
import { LineChart } from "@/shared/components/charts";
import type { Violation } from "../types";

const SEVERITY_COLORS: Record<string, string> = {
  block: "var(--destructive)",
  warning: "var(--warning)",
  breach: "var(--accent-orange)",
};

/**
 * Build a 30-day date range ending today, then bucket violations by date + severity.
 */
function buildTrendData(violations: Violation[]) {
  const today = new Date();
  today.setHours(23, 59, 59, 999);
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 29);
  thirtyDaysAgo.setHours(0, 0, 0, 0);

  // Generate 30 date keys (YYYY-MM-DD)
  const dateKeys: string[] = [];
  for (let d = new Date(thirtyDaysAgo); d <= today; d.setDate(d.getDate() + 1)) {
    dateKeys.push(d.toISOString().slice(0, 10));
  }

  // Bucket violations by date and severity
  const buckets: Record<string, Record<string, number>> = {};
  for (const key of dateKeys) {
    buckets[key] = { block: 0, warning: 0, breach: 0 };
  }

  for (const v of violations) {
    const dateKey = v.detected_at.slice(0, 10);
    if (buckets[dateKey]) {
      const sev = v.severity as string;
      if (sev in buckets[dateKey]) {
        buckets[dateKey][sev]++;
      }
    }
  }

  // Build series per severity (only include series with > 0 total)
  const severities = ["block", "warning", "breach"] as const;
  const series = severities
    .map((sev) => {
      const data = dateKeys.map((key) => ({ x: key, y: buckets[key][sev] }));
      const total = data.reduce((s, d) => s + d.y, 0);
      return { data, color: SEVERITY_COLORS[sev], label: sev, total };
    })
    .filter((s) => s.total > 0);

  // Also build a "total" series
  const totalData = dateKeys.map((key) => ({
    x: key,
    y: buckets[key].block + buckets[key].warning + buckets[key].breach,
  }));

  return { series, totalData, dateKeys };
}

interface ViolationsTrendChartProps {
  violations: Violation[];
}

export function ViolationsTrendChart({ violations }: ViolationsTrendChartProps) {
  const { series, totalData } = useMemo(() => buildTrendData(violations), [violations]);

  // If there are multiple severity types with data, show stacked by severity.
  // Otherwise show a single "total" line.
  const chartSeries = useMemo(() => {
    if (series.length > 1) {
      return series;
    }
    if (series.length === 1) {
      return series;
    }
    // No violations at all — show flat zero line
    return [{ data: totalData, color: "var(--muted-foreground)", label: "Violations" }];
  }, [series, totalData]);

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
        Violations Trend — 30 Days
      </p>
      <LineChart
        series={chartSeries}
        height={180}
        showXLabels
        xLabelInterval={7}
        formatY={(v) => String(Math.round(v))}
      />
    </div>
  );
}
