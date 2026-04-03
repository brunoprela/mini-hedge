import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { PortfolioInfo, PortfolioSummary, Position, PositionLot, TradeRequest } from "./types";

export type { PortfolioInfo, PortfolioSummary, Position, PositionLot };

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

export function portfolioSummaryQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["portfolio-summary", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<PortfolioSummary>(`/portfolios/${portfolioId}/summary`, {
        fundSlug,
      }),
    refetchInterval: 30_000,
  });
}

export function lotsQueryOptions(fundSlug: string, portfolioId: string, instrumentId: string) {
  return queryOptions({
    queryKey: ["lots", fundSlug, portfolioId, instrumentId],
    queryFn: () =>
      clientFetch<PositionLot[]>(`/portfolios/${portfolioId}/positions/${instrumentId}/lots`, {
        fundSlug,
      }),
  });
}

export function portfoliosQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["portfolios", fundSlug],
    queryFn: () => clientFetch<PortfolioInfo[]>("/portfolios", { fundSlug }),
    staleTime: 60_000,
  });
}

export async function executeTrade(fundSlug: string, trade: TradeRequest): Promise<Position> {
  return clientFetch<Position>("/portfolios/trades", {
    fundSlug,
    method: "POST",
    body: trade,
  });
}
