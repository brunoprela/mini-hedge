import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type {
  CapitalAccountSummary,
  CapitalTransaction,
  FundCapitalOverview,
  InvestorInfo,
} from "./types";

export function investorsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["investors", fundSlug],
    queryFn: () => clientFetch<InvestorInfo[]>("/capital/investors", { fundSlug }),
    staleTime: 60_000,
  });
}

export function capitalAccountsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["capital-accounts", fundSlug],
    queryFn: () => clientFetch<CapitalAccountSummary[]>("/capital/accounts", { fundSlug }),
    staleTime: 60_000,
  });
}

export function capitalOverviewQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["capital-overview", fundSlug],
    queryFn: () => clientFetch<FundCapitalOverview>("/capital/overview", { fundSlug }),
    staleTime: 60_000,
  });
}

export function investorHistoryQueryOptions(fundSlug: string, investorId: string) {
  return queryOptions({
    queryKey: ["investor-history", fundSlug, investorId],
    queryFn: () =>
      clientFetch<CapitalAccountSummary[]>(`/capital/investors/${investorId}/history`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export function investorTransactionsQueryOptions(fundSlug: string, investorId: string) {
  return queryOptions({
    queryKey: ["investor-transactions", fundSlug, investorId],
    queryFn: () =>
      clientFetch<CapitalTransaction[]>(`/capital/investors/${investorId}/transactions`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export async function processSubscription(
  fundSlug: string,
  data: {
    investor_id: string;
    amount: number | string;
    nav_per_share: number | string;
    business_date: string;
    portfolio_id?: string | null;
    currency?: string;
    share_class?: string;
    notes?: string | null;
  },
): Promise<CapitalAccountSummary> {
  return clientFetch<CapitalAccountSummary>("/capital/subscriptions", {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export async function createInvestor(
  fundSlug: string,
  data: { name: string; entity_type: string; email?: string; tax_id?: string },
): Promise<InvestorInfo> {
  return clientFetch<InvestorInfo>("/capital/investors", {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export async function processRedemption(
  fundSlug: string,
  data: {
    investor_id: string;
    amount: number | string;
    nav_per_share: number | string;
    business_date: string;
    portfolio_id?: string | null;
    currency?: string;
    notes?: string | null;
  },
): Promise<CapitalAccountSummary> {
  return clientFetch<CapitalAccountSummary>("/capital/redemptions", {
    fundSlug,
    method: "POST",
    body: data,
  });
}
