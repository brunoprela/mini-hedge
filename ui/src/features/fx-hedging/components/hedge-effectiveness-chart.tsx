"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { exposureQueryOptions } from "@/features/exposure/api";
import { LineChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { fxForwardsQueryOptions, fxHedgingSummaryQueryOptions } from "../api";

// ─── Types ────────────────────────────────────────────────

type Period = "30D" | "90D" | "1Y";

const PERIOD_DAYS: Record<Period, number> = {
  "30D": 30,
  "90D": 90,
  "1Y": 365,
};

// ─── Helpers ──────────────────────────────────────────────

function fmtDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function daysBetween(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/**
 * Derive a historical hedge effectiveness time-series from available forward
 * contract data. Since the API does not expose daily snapshots, we reconstruct
 * a per-day picture:
 *
 *   effectiveness(t) = sum(active_notional(t)) / total_exposure(t) * 100
 *
 * Active forwards on day `t` = those with trade_date <= t && maturity_date >= t
 * and status in ["open", "settled", "rolled", "closed"].
 *
 * We also produce a per-currency hedge-ratio series.
 */
function buildEffectivenessTimeSeries(
  forwards: {
    base_currency: string;
    notional: string;
    trade_date: string;
    maturity_date: string;
    status: string;
    mtm_value?: string | null;
  }[],
  currencyExposures: Record<string, number>,
  days: number,
) {
  const today = new Date();
  const start = new Date(today);
  start.setDate(start.getDate() - days);

  // Determine all currencies with exposure
  const currencies = Object.keys(currencyExposures).filter(
    (c) => currencyExposures[c] > 0,
  );
  const totalExposure = Object.values(currencyExposures).reduce(
    (a, b) => a + b,
    0,
  );

  if (totalExposure === 0 && forwards.length === 0) return { overall: [], perCurrency: {} };

  // Pre-parse forward dates
  const parsedForwards = forwards.map((f) => ({
    ...f,
    tradeDate: new Date(f.trade_date),
    maturityDate: new Date(f.maturity_date),
    notionalNum: Math.abs(Number(f.notional)),
  }));

  const overall: { x: string; y: number }[] = [];
  const perCurrency: Record<string, { x: string; y: number }[]> = {};
  for (const ccy of currencies) {
    perCurrency[ccy] = [];
  }

  // Walk each day
  const cursor = new Date(start);
  while (cursor <= today) {
    const dateStr = fmtDate(cursor);

    // Active notional per currency on this day
    const activeNotionalByCcy: Record<string, number> = {};
    for (const f of parsedForwards) {
      if (f.tradeDate <= cursor && f.maturityDate >= cursor) {
        activeNotionalByCcy[f.base_currency] =
          (activeNotionalByCcy[f.base_currency] ?? 0) + f.notionalNum;
      }
    }

    // Overall effectiveness: sum of hedged notional / total exposure
    let totalHedged = 0;
    for (const ccy of currencies) {
      const hedged = activeNotionalByCcy[ccy] ?? 0;
      const exp = currencyExposures[ccy] ?? 0;
      const ratio = exp > 0 ? Math.min(hedged / exp, 1.5) : 0;
      perCurrency[ccy]?.push({ x: dateStr, y: ratio * 100 });
      totalHedged += Math.min(hedged, exp);
    }

    // Also add hedged notional for currencies not in exposure (over-hedging)
    for (const [ccy, notional] of Object.entries(activeNotionalByCcy)) {
      if (!currencies.includes(ccy)) {
        totalHedged += notional;
      }
    }

    const overallRatio =
      totalExposure > 0
        ? Math.min((totalHedged / totalExposure) * 100, 150)
        : 0;

    overall.push({ x: dateStr, y: overallRatio });
    cursor.setDate(cursor.getDate() + 1);
  }

  return { overall, perCurrency };
}

// ─── Component ────────────────────────────────────────────

export function HedgeEffectivenessChart({
  portfolioId,
}: {
  portfolioId: string;
}) {
  const { fundSlug } = useFundContext();
  const [period, setPeriod] = useState<Period>("90D");

  const { data: forwards } = useQuery(
    fxForwardsQueryOptions(fundSlug, portfolioId),
  );
  const { data: summary } = useQuery(
    fxHedgingSummaryQueryOptions(fundSlug, portfolioId),
  );
  const { data: exposure } = useQuery(
    exposureQueryOptions(fundSlug, portfolioId),
  );

  if (!forwards || !summary || !exposure) {
    return (
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-xs text-[var(--muted-foreground)]">
          Loading hedge effectiveness...
        </p>
      </div>
    );
  }

  // Build currency exposure map from exposure breakdowns
  const currencyExposures: Record<string, number> = {};
  for (const bd of exposure.breakdowns?.currency ?? []) {
    const net = Math.abs(Number(bd.net_value));
    if (net > 0) {
      currencyExposures[bd.key] = net;
    }
  }

  const days = PERIOD_DAYS[period];
  const { overall, perCurrency } = buildEffectivenessTimeSeries(
    forwards,
    currencyExposures,
    days,
  );

  if (overall.length < 2) {
    return (
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-sm text-[var(--muted-foreground)]">
          Not enough data to display hedge effectiveness
        </p>
      </div>
    );
  }

  // Compute label interval based on period
  const xLabelInterval = period === "30D" ? 5 : period === "90D" ? 14 : 60;

  // Build series: overall + per-currency
  const CURRENCY_COLORS: Record<string, string> = {
    EUR: "#6366f1",
    GBP: "#06b6d4",
    JPY: "#f59e0b",
    CHF: "#8b5cf6",
    AUD: "#14b8a6",
    CAD: "#ec4899",
    NZD: "#84cc16",
    SEK: "#f97316",
    NOK: "#a855f7",
    SGD: "#0ea5e9",
  };

  const currencyKeys = Object.keys(perCurrency).filter(
    (k) => perCurrency[k].length >= 2,
  );

  // 100% reference line — same x-values as overall, constant y=100
  const refData = overall.map((pt) => ({ x: pt.x, y: 100 }));

  const series = [
    {
      data: refData,
      color: "var(--muted-foreground)",
      label: "100% target",
      dashed: true,
    },
    {
      data: overall,
      color: "var(--primary)",
      label: "Overall",
    },
    ...currencyKeys.map((ccy) => ({
      data: perCurrency[ccy],
      color: CURRENCY_COLORS[ccy] ?? "var(--muted-foreground)",
      label: ccy,
      dashed: true,
    })),
  ];

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Hedge Effectiveness
        </p>
        <div className="flex gap-1">
          {(["30D", "90D", "1Y"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                period === p
                  ? "bg-[var(--primary)] text-white"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <LineChart
        series={series}
        height={220}
        showXLabels
        xLabelInterval={xLabelInterval}
        formatY={(v) => `${v.toFixed(0)}%`}
      />
      <p className="mt-2 text-[10px] text-[var(--muted-foreground)]">
        Hedge ratio over time — dashed line at 100% indicates full coverage.
        Derived from active forward notional vs currency exposure.
      </p>
    </div>
  );
}
