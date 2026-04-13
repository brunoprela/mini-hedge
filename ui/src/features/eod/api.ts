import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { EODRunResult, EODRunSummary, NAVHistoryPoint } from "./types";

export function eodStatusQueryOptions(fundSlug: string, businessDate: string) {
  return queryOptions({
    queryKey: ["eod-status", fundSlug, businessDate],
    queryFn: () => clientFetch<EODRunResult | null>(`/eod/status/${businessDate}`, { fundSlug }),
    staleTime: 15_000,
  });
}

export function eodHistoryQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["eod-history", fundSlug],
    queryFn: () => clientFetch<EODRunSummary[]>("/eod/history?limit=20", { fundSlug }),
    staleTime: 30_000,
  });
}

export function navHistoryQueryOptions(fundSlug: string, period: "30d" | "90d" | "1y" = "90d") {
  return queryOptions({
    queryKey: ["nav-history", fundSlug, period],
    queryFn: () =>
      clientFetch<NAVHistoryPoint[]>(`/eod/nav/history?period=${period}`, { fundSlug }),
    staleTime: 60_000,
  });
}

export async function triggerEODRun(fundSlug: string, businessDate: string): Promise<EODRunResult> {
  return clientFetch<EODRunResult>("/eod/run", {
    fundSlug,
    method: "POST",
    body: { business_date: businessDate },
  });
}
