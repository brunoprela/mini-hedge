import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";

export function riskSnapshotQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["risk-snapshot", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/risk/{portfolio_id}/snapshot",
        {
          params: { path: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function stressTestsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["stress-tests", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/risk/{portfolio_id}/stress",
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

export function factorDecompositionQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["factor-decomposition", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/risk/{portfolio_id}/factors",
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

export async function takeRiskSnapshot(fundSlug: string, portfolioId: string) {
  const { data, error } = await api.POST(
    "/api/v1/risk/{portfolio_id}/snapshot",
    {
      params: { path: { portfolio_id: portfolioId } },
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  return data;
}

export async function runCustomStressTest(
  fundSlug: string,
  portfolioId: string,
  input: { name: string; shocks: Record<string, number>; description?: string },
) {
  const { data, error } = await api.POST(
    "/api/v1/risk/{portfolio_id}/stress",
    {
      params: { path: { portfolio_id: portfolioId } },
      // `description` has a backend default of "" but is marked required in
      // the OpenAPI schema; supply empty string when caller omits it.
      body: { ...input, description: input.description ?? "" },
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  return data;
}

export function riskHistoryQueryOptions(fundSlug: string, portfolioId: string) {
  const end = new Date().toISOString();
  const start = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  return queryOptions({
    queryKey: ["risk-history", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/risk/{portfolio_id}/snapshot/history",
        {
          params: {
            path: { portfolio_id: portfolioId },
            query: { start, end },
          },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 120_000,
  });
}
