import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { FeeAccrual, FeeSchedule } from "./types";

export function feeScheduleQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["fee-schedule", fundSlug],
    queryFn: () => clientFetch<FeeSchedule>(`/funds/${fundSlug}/fees/schedule`, { fundSlug }),
    staleTime: 120_000,
  });
}

export function feeAccrualsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["fee-accruals", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<FeeAccrual[]>(`/funds/${fundSlug}/fees/accruals?portfolio_id=${portfolioId}`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}
