import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { OrderSummary } from "@mini-hedge/api-types";

export function cashBalancesQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["cash-balances", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/cash/{portfolio_id}/balances", {
        params: { path: { portfolio_id: portfolioId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function settlementsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["settlements", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/cash/{portfolio_id}/settlements", {
        params: { path: { portfolio_id: portfolioId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function settlementLadderQueryOptions(
  fundSlug: string,
  portfolioId: string,
  horizonDays = 10,
) {
  return queryOptions({
    queryKey: ["settlement-ladder", fundSlug, portfolioId, horizonDays],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/cash/{portfolio_id}/ladder", {
        params: {
          path: { portfolio_id: portfolioId },
          query: { horizon_days: horizonDays },
        },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
  });
}

export function cashProjectionQueryOptions(
  fundSlug: string,
  portfolioId: string,
  horizonDays = 30,
) {
  return queryOptions({
    queryKey: ["cash-projection", fundSlug, portfolioId, horizonDays],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/cash/{portfolio_id}/projection", {
        params: {
          path: { portfolio_id: portfolioId },
          query: { horizon_days: horizonDays },
        },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
  });
}

/** Active (non-terminal) order states whose cash impact is not yet settled. */
const PENDING_ORDER_STATES = [
  "pending_compliance",
  "approved",
  "sent",
  "working",
  "partially_filled",
] as const;

export function pendingOrdersQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["pending-orders-for-projection", fundSlug, portfolioId],
    queryFn: async () => {
      const results = await Promise.all(
        PENDING_ORDER_STATES.map(async (state) => {
          const { data, error } = await api.GET("/api/v1/orders", {
            params: { query: { portfolio_id: portfolioId, state } },
            headers: fundHeaders(fundSlug),
          });
          if (error) throw error;
          return (data ?? []) as OrderSummary[];
        }),
      );
      return results.flat();
    },
    staleTime: 60_000,
  });
}
