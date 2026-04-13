"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { HBarChart } from "@/shared/components/charts";
import { InstrumentLink } from "@/shared/components/instrument-link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { exposureDrilldownQueryOptions, exposureQueryOptions } from "../api";
import type { ExposureBreakdown } from "../types";

const DIMENSION_LABELS: Record<string, string> = {
  sector: "By Sector",
  country: "By Country",
  asset_class: "By Asset Class",
  instrument: "By Instrument",
  currency: "By Currency",
};

const CHART_DIMENSIONS = new Set(["sector", "country", "asset_class"]);
const DRILLDOWN_DIMENSIONS = new Set(["sector", "country", "asset_class"]);

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
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const canDrillDown = DRILLDOWN_DIMENSIONS.has(dimension);

  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      <div className="border-b border-[var(--table-border)] bg-[var(--table-header)] px-3 py-1">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          {title}
          {canDrillDown && (
            <span className="ml-1 font-normal normal-case tracking-normal">
              (click to expand)
            </span>
          )}
        </p>
      </div>
      <table className="min-w-full divide-y divide-[var(--border)] text-xs">
        <thead>
          <tr>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-left font-semibold text-[var(--muted-foreground)]">Name</th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">
              Long
            </th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">
              Short
            </th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">Net</th>
            <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]">Wt%</th>
            {dimension === "currency" && (
              <th scope="col" className="whitespace-nowrap px-2 py-1 text-right font-semibold text-[var(--muted-foreground)]" />
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--table-border)]">
          {items.map((row) => {
            const isExpanded = expandedKey === row.key;
            return (
              <BreakdownRow
                key={row.key}
                row={row}
                dimension={dimension}
                fundSlug={fundSlug}
                portfolioId={portfolioId}
                canDrillDown={canDrillDown}
                isExpanded={isExpanded}
                onToggle={() => setExpandedKey(isExpanded ? null : row.key)}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function BreakdownRow({
  row,
  dimension,
  fundSlug,
  portfolioId,
  canDrillDown,
  isExpanded,
  onToggle,
}: {
  row: ExposureBreakdown;
  dimension: string;
  fundSlug: string;
  portfolioId: string;
  canDrillDown: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className={`hover:bg-[var(--table-row-hover)] ${canDrillDown ? "cursor-pointer" : ""} ${isExpanded ? "bg-[var(--table-row-hover)]" : ""}`}
        onClick={canDrillDown ? onToggle : undefined}
      >
        <td className="px-2 py-1 font-medium">
          <span className="flex items-center gap-1">
            {canDrillDown && (
              <span
                className="inline-block w-3 text-[10px] text-[var(--muted-foreground)] transition-transform"
                style={{ transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)" }}
              >
                &#9654;
              </span>
            )}
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
          </span>
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
      {isExpanded && canDrillDown && (
        <DrilldownRows
          fundSlug={fundSlug}
          portfolioId={portfolioId}
          dimension={dimension}
          dimensionKey={row.key}
        />
      )}
    </>
  );
}

function DrilldownRows({
  fundSlug,
  portfolioId,
  dimension,
  dimensionKey,
}: {
  fundSlug: string;
  portfolioId: string;
  dimension: string;
  dimensionKey: string;
}) {
  const { data, isLoading } = useQuery(
    exposureDrilldownQueryOptions(fundSlug, portfolioId, dimension, dimensionKey),
  );

  if (isLoading) {
    return (
      <tr className="bg-[var(--table-header)]">
        <td colSpan={5} className="px-6 py-2 text-[10px] text-[var(--muted-foreground)]">
          Loading instruments...
        </td>
      </tr>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <tr className="bg-[var(--table-header)]">
        <td colSpan={5} className="px-6 py-2 text-[10px] text-[var(--muted-foreground)]">
          No instruments
        </td>
      </tr>
    );
  }

  return (
    <>
      {data.items.map((item) => (
        <tr
          key={item.instrument_id}
          className="bg-[var(--table-header)]"
        >
          <td className="py-1 pl-7 pr-2 font-medium">
            <InstrumentLink instrument={item.instrument_id} />
          </td>
          <td className="px-2 py-1 text-right font-mono text-[var(--muted-foreground)]">
            {fmt(item.long_value)}
          </td>
          <td className="px-2 py-1 text-right font-mono text-[var(--muted-foreground)]">
            {fmt(item.short_value)}
          </td>
          <td className="px-2 py-1 text-right font-mono text-[var(--muted-foreground)]">
            {fmt(item.net_value)}
          </td>
          <td className="px-2 py-1 text-right font-mono text-[var(--muted-foreground)]">
            {parseFloat(item.weight_pct).toFixed(1)}%
          </td>
        </tr>
      ))}
    </>
  );
}
