import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { PriceSnapshot } from "./types";

export type { PriceSnapshot };

export function priceHistoryQueryOptions(
  fundSlug: string,
  instrumentId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["prices", "history", fundSlug, instrumentId, start, end],
    queryFn: () =>
      clientFetch<PriceSnapshot[]>(`/prices/history/${instrumentId}?start=${start}&end=${end}`, {
        fundSlug,
      }),
    staleTime: 30_000,
  });
}

export function latestPriceQueryOptions(fundSlug: string, instrumentId: string) {
  return queryOptions({
    queryKey: ["prices", "latest", fundSlug, instrumentId],
    queryFn: () =>
      clientFetch<PriceSnapshot>(`/prices/latest/${instrumentId}`, {
        fundSlug,
      }),
    staleTime: 10_000,
  });
}
