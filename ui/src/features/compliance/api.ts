import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { Violation } from "./types";

export function violationsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["violations", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<Violation[]>(`/compliance/violations?portfolio_id=${portfolioId}`, { fundSlug }),
    refetchInterval: 30_000,
  });
}
