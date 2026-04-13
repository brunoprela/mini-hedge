import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { DimensionDrilldown, ExposureHistoryEntry, PortfolioExposure } from "./types";

export function exposureQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["exposure", fundSlug, portfolioId],
    queryFn: () => clientFetch<PortfolioExposure>(`/exposure/${portfolioId}`, { fundSlug }),
    staleTime: 60_000,
  });
}

export function exposureDrilldownQueryOptions(
  fundSlug: string,
  portfolioId: string,
  dimension: string,
  key: string,
) {
  return queryOptions({
    queryKey: ["exposure-drilldown", fundSlug, portfolioId, dimension, key],
    queryFn: () =>
      clientFetch<DimensionDrilldown>(
        `/exposure/${portfolioId}/drilldown?dimension=${encodeURIComponent(dimension)}&key=${encodeURIComponent(key)}`,
        { fundSlug },
      ),
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
    queryFn: () =>
      clientFetch<ExposureHistoryEntry[]>(
        `/exposure/${portfolioId}/history?start=${start}&end=${end}`,
        { fundSlug },
      ),
    staleTime: 120_000,
    enabled: Boolean(portfolioId && start && end),
  });
}
