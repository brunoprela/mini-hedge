import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { EODRunResult, NAVHistoryPoint } from "./types";

export function eodStatusQueryOptions(fundSlug: string, businessDate: string) {
  return queryOptions({
    queryKey: ["eod-status", fundSlug, businessDate],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eod/status/{business_date}", {
        params: { path: { business_date: businessDate } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return (data ?? null) as EODRunResult | null;
    },
    staleTime: 15_000,
  });
}

export function eodHistoryQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["eod-history", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eod/history", {
        params: { query: { limit: 20 } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 30_000,
  });
}

export function navHistoryQueryOptions(fundSlug: string, period: "30d" | "90d" | "1y" = "90d") {
  return queryOptions({
    queryKey: ["nav-history", fundSlug, period],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eod/nav/history", {
        params: { query: { period } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return (data ?? []) as NAVHistoryPoint[];
    },
    staleTime: 60_000,
  });
}

export async function triggerEODRun(fundSlug: string, businessDate: string): Promise<EODRunResult> {
  const { data, error } = await api.POST("/api/v1/eod/run", {
    body: { business_date: businessDate } as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as EODRunResult;
}
