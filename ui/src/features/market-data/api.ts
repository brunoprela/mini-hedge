import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { PriceSnapshot } from "./types";

export type { PriceSnapshot };

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
