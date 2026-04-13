import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { OrderSummary } from "@mini-hedge/api-types";
import type { CashBalance, CashProjection, SettlementLadder, SettlementRecord } from "./types";

export function cashBalancesQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["cash-balances", fundSlug, portfolioId],
    queryFn: () => clientFetch<CashBalance[]>(`/cash/${portfolioId}/balances`, { fundSlug }),
    staleTime: 60_000,
  });
}

export function settlementsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["settlements", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<SettlementRecord[]>(`/cash/${portfolioId}/settlements`, { fundSlug }),
    staleTime: 60_000,
  });
}

export function settlementLadderQueryOptions(
  fundSlug: string,
  portfolioId: string,
  horizonDays = 10,
) {
  return queryOptions({
    queryKey: ["settlement-ladder", fundSlug, portfolioId, horizonDays],
    queryFn: () =>
      clientFetch<SettlementLadder>(`/cash/${portfolioId}/ladder?horizon_days=${horizonDays}`, {
        fundSlug,
      }),
  });
}

export function cashProjectionQueryOptions(
  fundSlug: string,
  portfolioId: string,
  horizonDays = 30,
) {
  return queryOptions({
    queryKey: ["cash-projection", fundSlug, portfolioId, horizonDays],
    queryFn: () =>
      clientFetch<CashProjection>(`/cash/${portfolioId}/projection?horizon_days=${horizonDays}`, {
        fundSlug,
      }),
  });
}

/** Active (non-terminal) order states whose cash impact is not yet settled. */
const PENDING_ORDER_STATES = [
  "pending_compliance",
  "approved",
  "sent",
  "working",
  "partially_filled",
] as const;

export function pendingOrdersQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["pending-orders-for-projection", fundSlug, portfolioId],
    queryFn: async () => {
      const results = await Promise.all(
        PENDING_ORDER_STATES.map((state) =>
          clientFetch<OrderSummary[]>(`/orders?portfolio_id=${portfolioId}&state=${state}`, {
            fundSlug,
          }),
        ),
      );
      return results.flat();
    },
    staleTime: 60_000,
  });
}
