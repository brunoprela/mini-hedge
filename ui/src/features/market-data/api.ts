import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
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
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/prices/history/{instrument_id}",
        {
          params: {
            path: { instrument_id: instrumentId },
            query: { start, end },
          },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 30_000,
  });
}

export function latestPriceQueryOptions(fundSlug: string, instrumentId: string) {
  return queryOptions({
    queryKey: ["prices", "latest", fundSlug, instrumentId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/prices/latest/{instrument_id}",
        {
          params: { path: { instrument_id: instrumentId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 10_000,
  });
}
