import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { components } from "@mini-hedge/api-types";

type ExposureDimension = components["schemas"]["ExposureDimension"];

export function exposureQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["exposure", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/exposure/{portfolio_id}",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function exposureDrilldownQueryOptions(
  fundSlug: string,
  portfolioId: string,
  dimension: ExposureDimension | string,
  key: string,
) {
  return queryOptions({
    queryKey: ["exposure-drilldown", fundSlug, portfolioId, dimension, key],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/exposure/{portfolio_id}/drilldown",
        {
          params: {
            path: { portfolio_id: portfolioId },
            query: { dimension: dimension as ExposureDimension, key },
          },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
    enabled: Boolean(portfolioId && dimension && key),
  });
}

export function exposureHistoryQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["exposure-history", fundSlug, portfolioId, start, end],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/exposure/{portfolio_id}/history",
        {
          params: {
            path: { portfolio_id: portfolioId },
            query: { start, end },
          },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 120_000,
    enabled: Boolean(portfolioId && start && end),
  });
}
