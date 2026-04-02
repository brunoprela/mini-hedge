import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";

export interface Position {
  instrument_id: string;
  quantity: string;
  avg_cost: string;
  cost_basis: string;
  realized_pnl: string;
  market_price: string;
  market_value: string;
  unrealized_pnl: string;
  currency: string;
  last_updated: string;
}

export function positionsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["positions", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<Position[]>(`/portfolios/${portfolioId}/positions`, {
        fundSlug,
      }),
    refetchInterval: 5_000,
  });
}
