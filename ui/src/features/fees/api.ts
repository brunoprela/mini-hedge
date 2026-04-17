import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { FeeAccrualResponse, FeeScheduleResponse } from "./types";

export function feeScheduleQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["fee-schedule", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/funds/{fund_slug}/fees/schedule",
        {
          params: { path: { fund_slug: fundSlug } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data as FeeScheduleResponse;
    },
    staleTime: 120_000,
  });
}

export function feeAccrualsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["fee-accruals", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/funds/{fund_slug}/fees/accruals",
        {
          params: {
            path: { fund_slug: fundSlug },
            query: { portfolio_id: portfolioId },
          },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return (data ?? []) as FeeAccrualResponse[];
    },
    staleTime: 60_000,
  });
}

export async function updateFeeSchedule(
  fundSlug: string,
  body: {
    management_fee_bps: number;
    performance_fee_pct: number | string;
    hurdle_rate_pct: number | string;
    high_water_mark?: boolean;
    crystallization_frequency?: string;
    payment_frequency?: string;
  },
): Promise<FeeScheduleResponse> {
  const { data, error } = await api.PUT("/api/v1/funds/{fund_slug}/fees/schedule", {
    params: { path: { fund_slug: fundSlug } },
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as FeeScheduleResponse;
}
