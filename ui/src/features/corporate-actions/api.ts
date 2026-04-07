import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { ProcessedAction } from "./types";

export function corporateActionsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["corporate-actions", fundSlug],
    queryFn: () =>
      clientFetch<ProcessedAction[]>("/corporate-actions", {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export async function processCorporateActions(
  fundSlug: string,
  data: { portfolio_id: string; start_date: string; end_date: string },
): Promise<ProcessedAction[]> {
  const params = new URLSearchParams(data);
  return clientFetch<ProcessedAction[]>(`/corporate-actions/process?${params.toString()}`, {
    fundSlug,
    method: "POST",
  });
}
