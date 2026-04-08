"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { HBarChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { exposureQueryOptions } from "../api";
import type { ExposureBreakdown } from "../types";

const DIMENSION_LABELS: Record<string, string> = {
  sector: "By Sector",
  country: "By Country",
  asset_class: "By Asset Class",
  instrument: "By Instrument",
  currency: "By Currency",
};

const CHART_DIMENSIONS = new Set(["sector", "country", "asset_class"]);

function fmt(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmtCompact(v: number) {
  return Math.abs(v) >= 1_000_000
    ? `$${(v / 1_000_000).toFixed(1)}M`
    : `$${(v / 1_000).toFixed(0)}K`;
}

export function ExposureBreakdowns({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(exposureQueryOptions(fundSlug, portfolioId));

  if (isLoading || !data) return null;

  const dimensions = Object.entries(data.breakdowns).filter(([, items]) => items.length > 0);
  if (dimensions.length === 0) return null;

  const chartDims = dimensions.filter(([dim]) => CHART_DIMENSIONS.has(dim));

  return (
    <div className="space-y-2">
      {/* Chart dimensions in a row */}
      {chartDims.length > 0 && (
        <div
          className={`grid gap-2 ${chartDims.length >= 3 ? "grid-cols-3" : chartDims.length === 2 ? "grid-cols-2" : "grid-cols-1"}`}
        >
          {chartDims.map(([dim, items]) => (
            <div
              key={dim}
              className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3"
            >
              <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                {DIMENSION_LABELS[dim] ?? dim} — Net
              </p>
              <HBarChart
                items={items
                  .map((row) => ({ label: row.key, value: parseFloat(row.net_value) }))
                  .sort((a, b) => b.value - a.value)
                  .slice(0, 8)}
                formatValue={fmtCompact}
              />
            </div>
          ))}
        </div>
      )}

      {/* All dimensions as compact tables in a 2-col grid */}
      <div className="grid grid-cols-2 gap-2">
        {dimensions.map(([dim, items]) => (
          <BreakdownTable
            key={dim}
            title={DIMENSION_LABELS[dim] ?? dim}
            items={items}
            dimension={dim}
            fundSlug={fundSlug}
            portfolioId={portfolioId}
          />
        ))}
      </div>
    </div>
  );
}

function BreakdownTable({
  title,
  items,
  dimension,
  fundSlug,
  portfolioId,
}: {
  title: string;
  items: ExposureBreakdown[];
  dimension: string;
  fundSlug: string;
  portfolioId: string;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      <div className="border-b border-[var(--table-border)] bg-[var(--table-header)] px-3 py-1">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          {title}
        </p>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
            <th className="px-2 py-1 text-left font-medium text-[var(--muted-foreground)]">Name</th>
            <th className="px-2 py-1 text-right font-medium text-[var(--muted-foreground)]">
              Long
            </th>
            <th className="px-2 py-1 text-right font-medium text-[var(--muted-foreground)]">
              Short
            </th>
            <th className="px-2 py-1 text-right font-medium text-[var(--muted-foreground)]">Net</th>
            <th className="px-2 py-1 text-right font-medium text-[var(--muted-foreground)]">Wt%</th>
            {dimension === "currency" && (
              <th className="px-2 py-1 text-right font-medium text-[var(--muted-foreground)]" />
            )}
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr
              key={row.key}
              className="border-b border-[var(--table-border)] last:border-b-0 hover:bg-[var(--table-row-hover)]"
            >
              <td className="px-2 py-1 font-medium">
                {dimension === "instrument" ? (
                  <Link
                    href={`/${fundSlug}/portfolio/${portfolioId}#positions`}
                    className="text-[var(--foreground)] hover:underline"
                  >
                    {row.key}
                  </Link>
                ) : dimension === "currency" ? (
                  <Link
                    href={`/${fundSlug}/fx-hedging`}
                    className="text-[var(--foreground)] hover:underline"
                  >
                    {row.key}
                  </Link>
                ) : (
                  row.key
                )}
              </td>
              <td className="px-2 py-1 text-right font-mono">{fmt(row.long_value)}</td>
              <td className="px-2 py-1 text-right font-mono">{fmt(row.short_value)}</td>
              <td className="px-2 py-1 text-right font-mono">{fmt(row.net_value)}</td>
              <td className="px-2 py-1 text-right font-mono">
                {parseFloat(row.weight_pct).toFixed(1)}%
              </td>
              {dimension === "currency" && (
                <td className="px-2 py-1 text-right">
                  <Link
                    href={`/${fundSlug}/fx-hedging`}
                    className="text-[10px] font-medium text-[var(--primary)] hover:underline"
                  >
                    Hedge
                  </Link>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
