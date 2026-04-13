"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { LineChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { navHistoryQueryOptions } from "../api";

type Period = "30d" | "90d" | "1y";

const PERIODS: { label: string; value: Period }[] = [
  { label: "30D", value: "30d" },
  { label: "90D", value: "90d" },
  { label: "1Y", value: "1y" },
];

function formatNav(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function formatNavFull(v: number): string {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function formatNavPerShare(v: number): string {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Compact delta indicator: triangle glyph with green/red coloring */
function NavDelta({
  value,
  pct,
  label,
}: {
  value: number;
  pct: number;
  label?: string;
}) {
  const direction = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const color =
    direction === "up"
      ? "var(--success)"
      : direction === "down"
        ? "var(--destructive)"
        : "var(--muted-foreground)";
  const arrow = direction === "up" ? "\u25B2" : direction === "down" ? "\u25BC" : "\u25C6";
  const absPct = Math.abs(pct);
  const pctStr = absPct < 0.01 ? "0.00%" : `${absPct.toFixed(2)}%`;

  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] font-medium leading-none"
      style={{ color }}
    >
      <span className="text-[9px]">{arrow}</span>
      {formatNavFull(Math.abs(value))}
      <span className="opacity-70">({pctStr})</span>
      {label && (
        <span className="font-normal text-[var(--muted-foreground)]">{label}</span>
      )}
    </span>
  );
}

export function NAVHistoryChart() {
  const { fundSlug } = useFundContext();
  const [period, setPeriod] = useState<Period>("90d");
  const { data: history, isLoading } = useQuery(navHistoryQueryOptions(fundSlug, period));

  const chartData =
    history?.map((p) => ({
      x: p.business_date,
      y: typeof p.nav === "string" ? Number.parseFloat(p.nav) : p.nav,
    })) ?? [];

  const xLabelInterval = Math.max(1, Math.floor(chartData.length / 6));

  // Compute day-over-day deltas from the two most recent history points
  const navDelta = useMemo(() => {
    if (!history || history.length < 2) return null;
    const latest = history[history.length - 1];
    const prev = history[history.length - 2];
    const latestNav = typeof latest.nav === "string" ? Number.parseFloat(latest.nav) : latest.nav;
    const prevNav = typeof prev.nav === "string" ? Number.parseFloat(prev.nav) : prev.nav;
    const latestNps =
      typeof latest.nav_per_share === "string"
        ? Number.parseFloat(latest.nav_per_share)
        : latest.nav_per_share;
    const prevNps =
      typeof prev.nav_per_share === "string"
        ? Number.parseFloat(prev.nav_per_share)
        : prev.nav_per_share;

    return {
      currentNav: latestNav,
      currentNps: latestNps,
      navChange: latestNav - prevNav,
      navChangePct: prevNav !== 0 ? ((latestNav - prevNav) / prevNav) * 100 : 0,
      npsChange: latestNps - prevNps,
      npsChangePct: prevNps !== 0 ? ((latestNps - prevNps) / prevNps) * 100 : 0,
      latestDate: latest.business_date,
      prevDate: prev.business_date,
    };
  }, [history]);

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      {/* NAV summary strip with delta indicators */}
      {navDelta && (
        <div className="mb-3 flex items-end gap-6 border-b border-[var(--border)] pb-3">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
              Fund NAV
            </p>
            <p className="mt-0.5 font-mono text-lg font-bold">
              {formatNavFull(navDelta.currentNav)}
            </p>
            <div className="mt-0.5">
              <NavDelta
                value={navDelta.navChange}
                pct={navDelta.navChangePct}
                label="vs prev day"
              />
            </div>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
              NAV / Share
            </p>
            <p className="mt-0.5 font-mono text-lg font-bold">
              {formatNavPerShare(navDelta.currentNps)}
            </p>
            <div className="mt-0.5">
              <NavDelta
                value={navDelta.npsChange}
                pct={navDelta.npsChangePct}
                label="vs prev day"
              />
            </div>
          </div>
          <div className="ml-auto text-right">
            <p className="text-[10px] text-[var(--muted-foreground)]">
              As of {navDelta.latestDate}
            </p>
          </div>
        </div>
      )}

      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          NAV History
        </h2>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setPeriod(p.value)}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                period === p.value
                  ? "bg-[var(--primary)] text-white"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--sidebar-active)]"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-[200px] items-center justify-center text-sm text-[var(--muted-foreground)]">
          Loading...
        </div>
      ) : chartData.length < 2 ? (
        <div className="flex h-[200px] items-center justify-center text-sm text-[var(--muted-foreground)]">
          Not enough NAV data for this period. Run more EOD cycles to populate the chart.
        </div>
      ) : (
        <LineChart
          series={[{ data: chartData, color: "var(--primary)", label: "NAV" }]}
          height={200}
          formatY={formatNav}
          xLabelInterval={xLabelInterval}
        />
      )}
    </div>
  );
}
