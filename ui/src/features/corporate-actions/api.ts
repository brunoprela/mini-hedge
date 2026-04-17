import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { ProcessedAction } from "./types";

export function corporateActionsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["corporate-actions", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/corporate-actions", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data as unknown as ProcessedAction[];
    },
    staleTime: 60_000,
  });
}

export async function processCorporateActions(
  fundSlug: string,
  body: { portfolio_id?: string; start_date: string; end_date: string },
): Promise<ProcessedAction[]> {
  const { data, error } = await api.POST("/api/v1/corporate-actions/process", {
    body,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return (data ?? []) as unknown as ProcessedAction[];
}
