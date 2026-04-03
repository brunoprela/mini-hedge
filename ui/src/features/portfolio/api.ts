import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { Position } from "./types";

export type { Position };

export function positionsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["positions", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<Position[]>(`/portfolios/${portfolioId}/positions`, {
        fundSlug,
      }),
    refetchInterval: 30_000,
  });
}
