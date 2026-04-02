"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatPrice, formatTimestamp } from "@/shared/lib/formatters";
import { instrumentsQueryOptions } from "@/features/instruments/api";
import { latestPriceQueryOptions } from "../api";

export function PriceDashboard() {
  const { fundSlug } = useFundContext();
  const { data: instruments, isLoading } = useQuery(
    instrumentsQueryOptions(fundSlug)
  );

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {instruments?.slice(0, 12).map((inst) => (
        <PriceCard
          key={inst.id}
          fundSlug={fundSlug}
          instrumentId={inst.ticker}
          name={inst.name}
        />
      ))}
    </div>
  );
}

function PriceCard({
  fundSlug,
  instrumentId,
  name,
}: {
  fundSlug: string;
  instrumentId: string;
  name: string;
}) {
  const { data: price } = useQuery(
    latestPriceQueryOptions(fundSlug, instrumentId)
  );

  return (
    <div className="rounded-lg border border-[var(--border)] p-4">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-sm font-medium">{instrumentId}</span>
        {price && (
          <span className="text-xs text-[var(--muted-foreground)]">
            {formatTimestamp(price.timestamp)}
          </span>
        )}
      </div>
      <p className="text-xs text-[var(--muted-foreground)]">{name}</p>
      {price ? (
        <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">Bid</p>
            <p className="font-mono">{formatPrice(price.bid)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">Mid</p>
            <p className="font-mono font-medium">{formatPrice(price.mid)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">Ask</p>
            <p className="font-mono">{formatPrice(price.ask)}</p>
          </div>
        </div>
      ) : (
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          Awaiting price data...
        </p>
      )}
    </div>
  );
}
