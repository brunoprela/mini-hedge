import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type {
  PortfolioInfo,
  PortfolioSummary,
  Position,
  PositionLot,
  TradeRequest,
} from "./types";

export type { PortfolioInfo, PortfolioSummary, Position, PositionLot };

export function positionsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["positions", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/portfolios/{portfolio_id}/positions",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
  });
}

export function portfolioSummaryQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["portfolio-summary", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/portfolios/{portfolio_id}/summary",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
  });
}

export function lotsQueryOptions(fundSlug: string, portfolioId: string, instrumentId: string) {
  return queryOptions({
    queryKey: ["lots", fundSlug, portfolioId, instrumentId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/portfolios/{portfolio_id}/positions/{instrument_id}/lots",
        {
          params: {
            path: { portfolio_id: portfolioId, instrument_id: instrumentId },
          },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
  });
}

export function portfoliosQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["portfolios", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/portfolios", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export async function executeTrade(fundSlug: string, trade: TradeRequest) {
  const { data, error } = await api.POST("/api/v1/portfolios/trades", {
    body: trade,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data;
}

export async function createPortfolio(
  fundSlug: string,
  body: { name: string; strategy?: string; base_currency?: string },
): Promise<PortfolioInfo> {
  const { data, error } = await api.POST("/api/v1/portfolios", {
    body,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data;
}
