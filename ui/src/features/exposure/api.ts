import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { PortfolioExposure } from "./types";

export function exposureQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["exposure", fundSlug, portfolioId],
    queryFn: () => clientFetch<PortfolioExposure>(`/exposure/${portfolioId}`, { fundSlug }),
    staleTime: 60_000,
  });
}
