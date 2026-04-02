import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";

export interface PriceSnapshot {
  instrument_id: string;
  bid: string;
  ask: string;
  mid: string;
  timestamp: string;
  source: string;
}

export function latestPriceQueryOptions(
  fundSlug: string,
  instrumentId: string
) {
  return queryOptions({
    queryKey: ["prices", "latest", fundSlug, instrumentId],
    queryFn: () =>
      clientFetch<PriceSnapshot>(`/prices/latest/${instrumentId}`, {
        fundSlug,
      }),
    refetchInterval: 2_000,
  });
}
