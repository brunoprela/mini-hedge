import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { FundTCASummary, PortfolioTCAReport, TCAReport } from "./types";

export function orderTCAQueryOptions(fundSlug: string, orderId: string) {
  return queryOptions({
    queryKey: ["order-tca", fundSlug, orderId],
    queryFn: () =>
      clientFetch<TCAReport | null>(`/orders/${orderId}/tca`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export function portfolioTCAQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["portfolio-tca", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<PortfolioTCAReport>(`/orders/tca/portfolio/${portfolioId}`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export function fundTCASummaryQueryOptions(fundSlug: string, days?: number) {
  return queryOptions({
    queryKey: ["fund-tca-summary", fundSlug, days],
    queryFn: () =>
      clientFetch<FundTCASummary>(`/orders/tca/summary${days != null ? `?days=${days}` : ""}`, {
        fundSlug,
      }),
    staleTime: 120_000,
  });
}

export async function computeTCA(fundSlug: string, orderId: string): Promise<TCAReport> {
  return clientFetch<TCAReport>(`/orders/${orderId}/tca/compute`, {
    fundSlug,
    method: "POST",
  });
}
