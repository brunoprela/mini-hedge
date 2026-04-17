import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type {
  FXForwardClose,
  FXForwardContract,
  FXForwardCreate,
  FXForwardRoll,
  FXHedgingSummary,
  FXInterestRate,
  HedgeRecommendation,
  RollRecommendation,
} from "./types";

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function fxForwardsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["fx-forwards", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/fx-hedging/forwards/{portfolio_id}",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return (data ?? []) as FXForwardContract[];
    },
    staleTime: 30_000,
  });
}

export function fxHedgingSummaryQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["fx-hedging-summary", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/fx-hedging/summary/{portfolio_id}",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data as FXHedgingSummary;
    },
    staleTime: 30_000,
  });
}

export function hedgeRecommendationsQueryOptions(
  fundSlug: string,
  portfolioId: string,
  hedgeRatio = "1.0",
  tenorDays = 30,
) {
  return queryOptions({
    queryKey: ["hedge-recommendations", fundSlug, portfolioId, hedgeRatio, tenorDays],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/fx-hedging/recommendations/{portfolio_id}/hedges",
        {
          params: {
            path: { portfolio_id: portfolioId },
            query: { hedge_ratio: hedgeRatio, tenor_days: tenorDays },
          },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return (data ?? []) as unknown as HedgeRecommendation[];
    },
    staleTime: 60_000,
  });
}

export function rollRecommendationsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["roll-recommendations", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/fx-hedging/recommendations/{portfolio_id}/rolls",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return (data ?? []) as unknown as RollRecommendation[];
    },
    staleTime: 60_000,
  });
}

export function fxInterestRatesQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["fx-interest-rates", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/fx-hedging/interest-rates", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return (data ?? []) as FXInterestRate[];
    },
    staleTime: 120_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export async function openForward(
  fundSlug: string,
  body: FXForwardCreate,
): Promise<FXForwardContract> {
  const { data, error } = await api.POST("/api/v1/fx-hedging/forwards", {
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as FXForwardContract;
}

export async function closeForward(
  fundSlug: string,
  forwardId: string,
  body: FXForwardClose,
): Promise<FXForwardContract> {
  const { data, error } = await api.POST(
    "/api/v1/fx-hedging/forwards/{forward_id}/close",
    {
      params: { path: { forward_id: forwardId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  return data as FXForwardContract;
}

export async function rollForward(
  fundSlug: string,
  forwardId: string,
  body: FXForwardRoll,
): Promise<FXForwardContract> {
  const { data, error } = await api.POST(
    "/api/v1/fx-hedging/forwards/{forward_id}/roll",
    {
      params: { path: { forward_id: forwardId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  return data as FXForwardContract;
}

export async function triggerMTM(fundSlug: string, portfolioId: string): Promise<void> {
  const { error } = await api.POST(
    "/api/v1/fx-hedging/forwards/{portfolio_id}/mtm",
    {
      params: { path: { portfolio_id: portfolioId } },
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
}

export async function setInterestRate(
  fundSlug: string,
  currency: string,
  rate: number | string,
  tenorDays = 30,
  source = "manual",
): Promise<void> {
  const { error } = await api.PUT(
    "/api/v1/fx-hedging/interest-rates/{currency}",
    {
      params: {
        path: { currency },
        query: { rate, tenor_days: tenorDays, source },
      },
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
}
