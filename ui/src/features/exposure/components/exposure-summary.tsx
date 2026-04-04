"use client";

import { useQuery } from "@tanstack/react-query";
import { InfoTooltip } from "@/shared/components/table-controls";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { exposureQueryOptions } from "../api";

export function ExposureSummary({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(exposureQueryOptions(fundSlug, portfolioId));

  if (isLoading || !data) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading exposure...</div>;
  }

  const fmt = (v: string) => {
    const n = parseFloat(v);
    return n.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    });
  };

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard
        label="Gross"
        value={fmt(data.gross_exposure)}
        info="Sum of absolute values of all positions (long + |short|)"
      />
      <StatCard
        label="Net"
        value={fmt(data.net_exposure)}
        info="Long exposure minus short exposure"
      />
      <StatCard
        label="Long"
        value={fmt(data.long_exposure)}
        sub={`${data.long_count} positions`}
        info="Total market value of long (bought) positions"
      />
      <StatCard
        label="Short"
        value={fmt(data.short_exposure)}
        sub={`${data.short_count} positions`}
        info="Total market value of short (sold) positions"
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  info,
}: {
  label: string;
  value: string;
  sub?: string;
  info?: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
        {label}
        {info && <InfoTooltip text={info} />}
      </p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
      {sub && <p className="text-xs text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  );
}
