"use client";

import { useQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { exposureQueryOptions } from "../api";
import type { PortfolioExposure, ExposureBreakdown } from "../types";

const DIMENSION_LABELS: Record<string, string> = {
  sector: "By Sector",
  country: "By Country",
  asset_class: "By Asset Class",
  currency: "By Currency",
};

/** Dimensions to show in comparison (skip instrument — too granular). */
const COMPARE_DIMENSIONS = ["sector", "country", "asset_class", "currency"];

const PORTFOLIO_COLORS = [
  "var(--primary)",
  "var(--warning)",
  "var(--success)",
  "var(--destructive)",
  "#8b5cf6",
  "#ec4899",
];

function fmt(v: number) {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmtCompact(v: number) {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

interface ExposureComparisonProps {
  fundSlug: string;
  portfolios: { id: string; name: string }[];
}

export function ExposureComparison({ fundSlug, portfolios }: ExposureComparisonProps) {
  const queries = useQueries({
    queries: portfolios.map((p) => ({
      ...exposureQueryOptions(fundSlug, p.id),
      enabled: true,
    })),
  });

  const isLoading = queries.some((q) => q.isLoading);
  const exposures = queries
    .map((q, i) => (q.data ? { portfolio: portfolios[i], data: q.data } : null))
    .filter(Boolean) as { portfolio: { id: string; name: string }; data: PortfolioExposure }[];

  if (isLoading) {
    return <p className="text-xs text-[var(--muted-foreground)]">Loading comparison...</p>;
  }

  if (exposures.length < 2) {
    return <p className="text-xs text-[var(--muted-foreground)]">Need at least 2 portfolios to compare.</p>;
  }

  return (
    <div className="space-y-3">
      {/* Summary comparison */}
      <SummaryComparison exposures={exposures} />

      {/* Dimension breakdowns */}
      {COMPARE_DIMENSIONS.map((dim) => (
        <DimensionComparison key={dim} dimension={dim} exposures={exposures} />
      ))}
    </div>
  );
}

function SummaryComparison({
  exposures,
}: {
  exposures: { portfolio: { id: string; name: string }; data: PortfolioExposure }[];
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      <div className="border-b border-[var(--table-border)] bg-[var(--table-header)] px-3 py-1">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Portfolio Summary Comparison
        </p>
      </div>
      <table className="min-w-full divide-y divide-[var(--border)] text-xs">
        <thead>
          <tr>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-left font-semibold text-[var(--muted-foreground)]">
              Portfolio
            </th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">
              Gross
            </th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">
              Net
            </th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">
              Long
            </th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">
              Short
            </th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">
              N/G Ratio
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--table-border)]">
          {exposures.map(({ portfolio, data }, i) => {
            const gross = Number(data.gross_exposure);
            const net = Number(data.net_exposure);
            const ratio = gross === 0 ? 0 : (net / gross) * 100;
            return (
              <tr
                key={portfolio.id}
                className="hover:bg-[var(--table-row-hover)]"
              >
                <td className="px-2 py-1 font-medium">
                  <span className="flex items-center gap-1.5">
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length] }}
                    />
                    {portfolio.name}
                  </span>
                </td>
                <td className="px-2 py-1 text-right font-mono">{fmt(gross)}</td>
                <td className="px-2 py-1 text-right font-mono">{fmt(net)}</td>
                <td className="px-2 py-1 text-right font-mono text-[var(--success)]">
                  {fmt(Number(data.long_exposure))}
                </td>
                <td className="px-2 py-1 text-right font-mono text-[var(--destructive)]">
                  {fmt(Number(data.short_exposure))}
                </td>
                <td className="px-2 py-1 text-right font-mono">{ratio.toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DimensionComparison({
  dimension,
  exposures,
}: {
  dimension: string;
  exposures: { portfolio: { id: string; name: string }; data: PortfolioExposure }[];
}) {
  // Collect all keys across portfolios for this dimension
  const merged = useMemo(() => {
    const keySet = new Set<string>();
    const byPortfolio = new Map<string, Map<string, ExposureBreakdown>>();

    for (const { portfolio, data } of exposures) {
      const items = data.breakdowns[dimension] ?? [];
      const map = new Map<string, ExposureBreakdown>();
      for (const item of items) {
        keySet.add(item.key);
        map.set(item.key, item);
      }
      byPortfolio.set(portfolio.id, map);
    }

    // Sort keys by total absolute net value across portfolios (descending)
    const keys = [...keySet].sort((a, b) => {
      let totalA = 0;
      let totalB = 0;
      for (const map of byPortfolio.values()) {
        totalA += Math.abs(Number(map.get(a)?.net_value ?? 0));
        totalB += Math.abs(Number(map.get(b)?.net_value ?? 0));
      }
      return totalB - totalA;
    });

    return { keys, byPortfolio };
  }, [dimension, exposures]);

  if (merged.keys.length === 0) return null;

  // Find the max absolute net value for the bar chart scaling
  const maxAbsNet = useMemo(() => {
    let max = 0;
    for (const map of merged.byPortfolio.values()) {
      for (const item of map.values()) {
        max = Math.max(max, Math.abs(Number(item.net_value)));
      }
    }
    return max || 1;
  }, [merged.byPortfolio]);

  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      <div className="border-b border-[var(--table-border)] bg-[var(--table-header)] px-3 py-1">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          {DIMENSION_LABELS[dimension] ?? dimension} — Net Comparison
        </p>
      </div>
      <table className="min-w-full divide-y divide-[var(--border)] text-xs">
        <thead>
          <tr>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-left font-semibold text-[var(--muted-foreground)]">
              {dimension === "sector" ? "Sector" : dimension === "country" ? "Country" : dimension === "asset_class" ? "Asset Class" : "Currency"}
            </th>
            {exposures.map(({ portfolio }, i) => (
              <th
                key={portfolio.id}
                scope="col"
                className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]"
              >
                <span className="flex items-center justify-end gap-1">
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length] }}
                  />
                  {portfolio.name}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--table-border)]">
          {merged.keys.map((key) => (
            <tr
              key={key}
              className="hover:bg-[var(--table-row-hover)]"
            >
              <td className="px-2 py-1.5 font-medium">{key}</td>
              {exposures.map(({ portfolio }, i) => {
                const item = merged.byPortfolio.get(portfolio.id)?.get(key);
                const netVal = Number(item?.net_value ?? 0);
                const barWidth = (Math.abs(netVal) / maxAbsNet) * 100;
                return (
                  <td key={portfolio.id} className="px-2 py-1.5">
                    <div className="flex items-center justify-end gap-2">
                      <div className="relative h-3 w-16 rounded bg-[var(--border)]">
                        {netVal !== 0 && (
                          <div
                            className="absolute top-0 h-3 rounded"
                            style={{
                              right: netVal >= 0 ? undefined : 0,
                              left: netVal >= 0 ? 0 : undefined,
                              width: `${Math.max(barWidth, 2)}%`,
                              backgroundColor: PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length],
                              opacity: 0.7,
                            }}
                          />
                        )}
                      </div>
                      <span className="w-16 text-right font-mono">
                        {item ? fmtCompact(netVal) : "—"}
                      </span>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
