"use client";

import { useQuery } from "@tanstack/react-query";
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
        <BreakdownTable key={dim} title={DIMENSION_LABELS[dim] ?? dim} items={items} />
      ))}
    </div>
  );
}

function BreakdownTable({ title, items }: { title: string; items: ExposureBreakdown[] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-[var(--muted-foreground)]">{title}</h3>
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
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
              <tr key={row.key} className="border-b border-[var(--border)] last:border-b-0">
                <td className="px-4 py-2 font-medium">{row.key}</td>
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
