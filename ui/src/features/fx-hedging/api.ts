import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
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
    queryFn: () =>
      clientFetch<FXForwardContract[]>(`/fx-hedging/forwards/${portfolioId}`, { fundSlug }),
    staleTime: 30_000,
  });
}

export function fxHedgingSummaryQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["fx-hedging-summary", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<FXHedgingSummary>(`/fx-hedging/summary/${portfolioId}`, { fundSlug }),
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
    queryFn: () =>
      clientFetch<HedgeRecommendation[]>(
        `/fx-hedging/recommendations/${portfolioId}/hedges?hedge_ratio=${hedgeRatio}&tenor_days=${tenorDays}`,
        { fundSlug },
      ),
    staleTime: 60_000,
  });
}

export function rollRecommendationsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["roll-recommendations", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<RollRecommendation[]>(`/fx-hedging/recommendations/${portfolioId}/rolls`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export function fxInterestRatesQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["fx-interest-rates", fundSlug],
    queryFn: () => clientFetch<FXInterestRate[]>("/fx-hedging/interest-rates", { fundSlug }),
    staleTime: 120_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export async function openForward(
  fundSlug: string,
  data: FXForwardCreate,
): Promise<FXForwardContract> {
  return clientFetch<FXForwardContract>("/fx-hedging/forwards", {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export async function closeForward(
  fundSlug: string,
  forwardId: string,
  data: FXForwardClose,
): Promise<FXForwardContract> {
  return clientFetch<FXForwardContract>(`/fx-hedging/forwards/${forwardId}/close`, {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export async function rollForward(
  fundSlug: string,
  forwardId: string,
  data: FXForwardRoll,
): Promise<FXForwardContract> {
  return clientFetch<FXForwardContract>(`/fx-hedging/forwards/${forwardId}/roll`, {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export async function triggerMTM(fundSlug: string, portfolioId: string): Promise<void> {
  await clientFetch(`/fx-hedging/forwards/${portfolioId}/mtm`, {
    fundSlug,
    method: "POST",
  });
}

export async function setInterestRate(
  fundSlug: string,
  currency: string,
  rate: number | string,
  tenorDays = 30,
  source = "manual",
): Promise<void> {
  await clientFetch(`/fx-hedging/interest-rates/${currency}?rate=${rate}&tenor_days=${tenorDays}&source=${source}`, {
    fundSlug,
    method: "PUT",
  });
}
