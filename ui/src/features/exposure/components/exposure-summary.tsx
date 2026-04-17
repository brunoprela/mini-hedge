"use client";

import { useQuery } from "@tanstack/react-query";
import { LoadingSkeleton } from "@mini-hedge/ui";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { exposureQueryOptions } from "../api";

const fmt = (v: string) => {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
};

/** Returns summary items for use in SectionPanel summary prop. */
export function useExposureSummary(portfolioId: string) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(exposureQueryOptions(fundSlug, portfolioId));

  if (isLoading || !data) return null;

  return [
    { label: "Gross", value: fmt(data.gross_exposure) },
    { label: "Net", value: fmt(data.net_exposure) },
    { label: "Long", value: `${fmt(data.long_exposure)} (${data.long_count})` },
    { label: "Short", value: `${fmt(data.short_exposure)} (${data.short_count})` },
  ];
}

/** Standalone component — renders as inline strip */
export function ExposureSummary({ portfolioId }: { portfolioId: string }) {
  const items = useExposureSummary(portfolioId);
  if (!items) return <LoadingSkeleton height="2.5rem" />;

  return (
    <div className="flex items-center gap-4 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span className="text-[10px] text-[var(--muted-foreground)]">{item.label}</span>
          <span className="font-mono text-xs font-semibold">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
