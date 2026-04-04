import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { FactorDecomposition, RiskSnapshot, StressTestResult } from "./types";

export function riskSnapshotQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["risk-snapshot", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<RiskSnapshot | null>(`/risk/${portfolioId}/snapshot`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export function stressTestsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["stress-tests", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<StressTestResult[]>(`/risk/${portfolioId}/stress`, {
        fundSlug,
      }),
  });
}

export function factorDecompositionQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["factor-decomposition", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<FactorDecomposition>(`/risk/${portfolioId}/factors`, {
        fundSlug,
      }),
  });
}

export async function takeRiskSnapshot(
  fundSlug: string,
  portfolioId: string,
): Promise<RiskSnapshot> {
  return clientFetch<RiskSnapshot>(`/risk/${portfolioId}/snapshot`, {
    fundSlug,
    method: "POST",
  });
}
