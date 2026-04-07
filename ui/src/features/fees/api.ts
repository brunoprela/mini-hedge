import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { FeeAccrualResponse, FeeScheduleResponse } from "./types";

export function feeScheduleQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["fee-schedule", fundSlug],
    queryFn: () =>
      clientFetch<FeeScheduleResponse>(`/funds/${fundSlug}/fees/schedule`, { fundSlug }),
    staleTime: 120_000,
  });
}

export function feeAccrualsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["fee-accruals", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<FeeAccrualResponse[]>(
        `/funds/${fundSlug}/fees/accruals?portfolio_id=${portfolioId}`,
        { fundSlug },
      ),
    staleTime: 60_000,
  });
}

export async function updateFeeSchedule(
  fundSlug: string,
  data: {
    management_fee_bps: number;
    performance_fee_pct: number | string;
    hurdle_rate_pct: number | string;
    high_water_mark?: boolean;
    crystallization_frequency?: string;
    payment_frequency?: string;
  },
): Promise<FeeScheduleResponse> {
  return clientFetch<FeeScheduleResponse>(`/funds/${fundSlug}/fees/schedule`, {
    fundSlug,
    method: "PUT",
    body: data,
  });
}
