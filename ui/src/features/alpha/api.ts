import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { HypotheticalTrade, OptimizationResult, WhatIfResult } from "./types";

export function scenariosQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["alpha-scenarios", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/alpha/{portfolio_id}/scenarios",
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

export function optimizationsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["alpha-optimizations", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/alpha/{portfolio_id}/optimizations",
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

export function orderIntentsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["alpha-intents", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/alpha/{portfolio_id}/intents", {
        params: { path: { portfolio_id: portfolioId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

export async function runWhatIf(
  fundSlug: string,
  portfolioId: string,
  body: { scenario_name: string; trades: HypotheticalTrade[] },
): Promise<WhatIfResult> {
  const { data, error } = await api.POST("/api/v1/alpha/{portfolio_id}/what-if", {
    params: { path: { portfolio_id: portfolioId } },
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as WhatIfResult;
}

export async function runOptimization(
  fundSlug: string,
  portfolioId: string,
  objective: string,
): Promise<OptimizationResult> {
  const { data, error } = await api.POST("/api/v1/alpha/{portfolio_id}/optimize", {
    params: { path: { portfolio_id: portfolioId } },
    body: { objective } as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as OptimizationResult;
}

export async function approveIntent(
  fundSlug: string,
  portfolioId: string,
  intentId: string,
): Promise<{ status: string }> {
  const { data, error } = await api.POST(
    "/api/v1/alpha/{portfolio_id}/intents/{intent_id}/approve",
    {
      params: { path: { portfolio_id: portfolioId, intent_id: intentId } },
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  return data as { status: string };
}

export async function cancelIntent(
  fundSlug: string,
  portfolioId: string,
  intentId: string,
): Promise<{ status: string }> {
  const { data, error } = await api.POST(
    "/api/v1/alpha/{portfolio_id}/intents/{intent_id}/cancel",
    {
      params: { path: { portfolio_id: portfolioId, intent_id: intentId } },
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  return data as { status: string };
}
