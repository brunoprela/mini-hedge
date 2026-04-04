import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type {
  HypotheticalTrade,
  OptimizationResult,
  OrderIntent,
  ScenarioRun,
  WhatIfResult,
} from "./types";

export function scenariosQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["alpha-scenarios", fundSlug, portfolioId],
    queryFn: () => clientFetch<ScenarioRun[]>(`/alpha/${portfolioId}/scenarios`, { fundSlug }),
  });
}

export function optimizationsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["alpha-optimizations", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<OptimizationResult[]>(`/alpha/${portfolioId}/optimizations`, { fundSlug }),
  });
}

export function orderIntentsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["alpha-intents", fundSlug, portfolioId],
    queryFn: () => clientFetch<OrderIntent[]>(`/alpha/${portfolioId}/intents`, { fundSlug }),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

export async function runWhatIf(
  fundSlug: string,
  portfolioId: string,
  body: { scenario_name: string; trades: HypotheticalTrade[] },
): Promise<WhatIfResult> {
  return clientFetch<WhatIfResult>(`/alpha/${portfolioId}/what-if`, {
    fundSlug,
    method: "POST",
    body,
  });
}

export async function runOptimization(
  fundSlug: string,
  portfolioId: string,
  objective: string,
): Promise<OptimizationResult> {
  return clientFetch<OptimizationResult>(`/alpha/${portfolioId}/optimize`, {
    fundSlug,
    method: "POST",
    body: { objective },
  });
}

export async function approveIntent(
  fundSlug: string,
  portfolioId: string,
  intentId: string,
): Promise<{ status: string }> {
  return clientFetch<{ status: string }>(`/alpha/${portfolioId}/intents/${intentId}/approve`, {
    fundSlug,
    method: "POST",
  });
}

export async function cancelIntent(
  fundSlug: string,
  portfolioId: string,
  intentId: string,
): Promise<{ status: string }> {
  return clientFetch<{ status: string }>(`/alpha/${portfolioId}/intents/${intentId}/cancel`, {
    fundSlug,
    method: "POST",
  });
}
