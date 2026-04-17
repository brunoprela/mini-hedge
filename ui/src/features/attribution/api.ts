import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type {
  BrinsonFachlerResult,
  CumulativeAttribution,
  FXAttributionResult,
  RiskBasedResult,
} from "./types";

export function brinsonFachlerQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["attribution", "brinson-fachler", fundSlug, portfolioId, start, end],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/attribution/{portfolio_id}/brinson-fachler",
        {
          params: { path: { portfolio_id: portfolioId }, query: { start, end } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data as BrinsonFachlerResult;
    },
    enabled: Boolean(portfolioId && start && end),
  });
}

export function riskBasedQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["attribution", "risk-based", fundSlug, portfolioId, start, end],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/attribution/{portfolio_id}/risk-based",
        {
          params: { path: { portfolio_id: portfolioId }, query: { start, end } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data as RiskBasedResult;
    },
    enabled: Boolean(portfolioId && start && end),
  });
}

export function cumulativeQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["attribution", "cumulative", fundSlug, portfolioId, start, end],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/attribution/{portfolio_id}/cumulative",
        {
          params: { path: { portfolio_id: portfolioId }, query: { start, end } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data as CumulativeAttribution;
    },
    enabled: Boolean(portfolioId && start && end),
  });
}

export function fxAttributionQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["attribution", "fx", fundSlug, portfolioId, start, end],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/attribution/{portfolio_id}/fx", {
        params: { path: { portfolio_id: portfolioId }, query: { start, end } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data as unknown as FXAttributionResult;
    },
    enabled: Boolean(portfolioId && start && end),
  });
}
