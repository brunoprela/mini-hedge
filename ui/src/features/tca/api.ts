import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { FundTCASummary, PortfolioTCAReport, TCAReport } from "./types";

export function orderTCAQueryOptions(fundSlug: string, orderId: string) {
  return queryOptions({
    queryKey: ["order-tca", fundSlug, orderId],
    queryFn: async (): Promise<TCAReport | null> => {
      const { data, error } = await api.GET("/api/v1/orders/{order_id}/tca", {
        params: { path: { order_id: orderId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data ?? null;
    },
    staleTime: 60_000,
  });
}

export function portfolioTCAQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["portfolio-tca", fundSlug, portfolioId],
    queryFn: async (): Promise<PortfolioTCAReport> => {
      const { data, error } = await api.GET(
        "/api/v1/orders/tca/portfolio/{portfolio_id}",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      if (!data) throw new Error("Empty portfolio TCA response");
      return data;
    },
    staleTime: 60_000,
  });
}

export function fundTCASummaryQueryOptions(fundSlug: string, days?: number) {
  return queryOptions({
    queryKey: ["fund-tca-summary", fundSlug, days],
    queryFn: async (): Promise<FundTCASummary> => {
      const { data, error } = await api.GET("/api/v1/orders/tca/summary", {
        params: { query: days != null ? { days } : {} },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      if (!data) throw new Error("Empty fund TCA summary response");
      return data;
    },
    staleTime: 120_000,
  });
}

export function brokerScorecardsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["broker-scorecards", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/brokers/scorecards", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 120_000,
  });
}

export async function computeTCA(fundSlug: string, orderId: string): Promise<TCAReport> {
  const { data, error } = await api.POST("/api/v1/orders/{order_id}/tca/compute", {
    params: { path: { order_id: orderId } },
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  if (!data) throw new Error("Empty TCA compute response");
  return data;
}
