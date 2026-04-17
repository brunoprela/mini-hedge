import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { CapitalAccountSummary, InvestorInfo } from "./types";

export function investorsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["investors", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/capital/investors", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function capitalAccountsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["capital-accounts", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/capital/accounts", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function capitalOverviewQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["capital-overview", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/capital/overview", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function investorHistoryQueryOptions(fundSlug: string, investorId: string) {
  return queryOptions({
    queryKey: ["investor-history", fundSlug, investorId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/capital/investors/{investor_id}/history",
        {
          params: { path: { investor_id: investorId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function investorTransactionsQueryOptions(fundSlug: string, investorId: string) {
  return queryOptions({
    queryKey: ["investor-transactions", fundSlug, investorId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/capital/investors/{investor_id}/transactions",
        {
          params: { path: { investor_id: investorId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export async function processSubscription(
  fundSlug: string,
  body: {
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
  const { data, error } = await api.POST("/api/v1/capital/subscriptions", {
    // Cast: UI-only partial payload shape differs slightly from generated SubscriptionRequest.
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as CapitalAccountSummary;
}

export async function createInvestor(
  fundSlug: string,
  body: { name: string; entity_type: string; contact_email?: string; tax_jurisdiction?: string },
): Promise<InvestorInfo> {
  const { data, error } = await api.POST("/api/v1/capital/investors", {
    // Cast: UI-only partial payload shape differs slightly from generated CreateInvestorRequest.
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as InvestorInfo;
}

export async function processRedemption(
  fundSlug: string,
  body: {
    investor_id: string;
    amount: number | string;
    nav_per_share: number | string;
    business_date: string;
    portfolio_id?: string | null;
    currency?: string;
    notes?: string | null;
  },
): Promise<CapitalAccountSummary> {
  const { data, error } = await api.POST("/api/v1/capital/redemptions", {
    // Cast: UI-only partial payload shape differs slightly from generated RedemptionRequest.
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as CapitalAccountSummary;
}
