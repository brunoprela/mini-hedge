"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
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

function fmt(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function ExposureBreakdowns({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(exposureQueryOptions(fundSlug, portfolioId));

  if (isLoading || !data) return null;

  const dimensions = Object.entries(data.breakdowns).filter(([, items]) => items.length > 0);

  if (dimensions.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No breakdown data available.</p>;
  }

  return (
    <div className="space-y-6">
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
    <div>
      <h3 className="mb-2 text-sm font-medium text-[var(--muted-foreground)]">{title}</h3>
      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
              <th className="px-4 py-2 text-left font-medium text-[var(--muted-foreground)]">
                Name
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                Long
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                Short
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                Net
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                Gross
              </th>
              <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                Weight
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr
                key={row.key}
                className="border-b border-[var(--table-border)] last:border-b-0 hover:bg-[var(--table-row-hover)]"
              >
                <td className="px-4 py-2 font-medium">
                  {dimension === "instrument" ? (
                    <Link
                      href={`/${fundSlug}/portfolio/${portfolioId}#positions`}
                      className="text-[var(--foreground)] underline-offset-2 hover:underline"
                    >
                      {row.key}
                    </Link>
                  ) : (
                    row.key
                  )}
                </td>
                <td className="px-4 py-2 text-right">{fmt(row.long_value)}</td>
                <td className="px-4 py-2 text-right">{fmt(row.short_value)}</td>
                <td className="px-4 py-2 text-right">{fmt(row.net_value)}</td>
                <td className="px-4 py-2 text-right">{fmt(row.gross_value)}</td>
                <td className="px-4 py-2 text-right">{parseFloat(row.weight_pct).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
