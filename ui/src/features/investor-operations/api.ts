import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type {
  FundTerms,
  InvestorKYC,
  QueueSummary,
  RedemptionRequest,
  SubscriptionRequest,
} from "./types";

// ---------------------------------------------------------------------------
//  Query options
// ---------------------------------------------------------------------------

export function subscriptionsQueryOptions(fundSlug: string, state?: string) {
  const params = state ? `?state=${state}` : "";
  return queryOptions({
    queryKey: ["subscriptions", fundSlug, state ?? "all"],
    queryFn: () =>
      clientFetch<SubscriptionRequest[]>(`/investor-operations/subscriptions${params}`, {
        fundSlug,
      }),
    staleTime: 30_000,
  });
}

export function redemptionsQueryOptions(fundSlug: string, state?: string) {
  const params = state ? `?state=${state}` : "";
  return queryOptions({
    queryKey: ["redemptions", fundSlug, state ?? "all"],
    queryFn: () =>
      clientFetch<RedemptionRequest[]>(`/investor-operations/redemptions${params}`, {
        fundSlug,
      }),
    staleTime: 30_000,
  });
}

export function queueSummaryQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["investor-ops-queue", fundSlug],
    queryFn: () =>
      clientFetch<QueueSummary>("/investor-operations/queue", { fundSlug }),
    staleTime: 30_000,
  });
}

export function fundTermsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["fund-terms", fundSlug],
    queryFn: () =>
      clientFetch<FundTerms[]>("/investor-operations/fund-terms", { fundSlug }),
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
//  Mutations
// ---------------------------------------------------------------------------

export async function submitSubscription(
  fundSlug: string,
  data: { investor_id: string; amount: string; share_class?: string },
): Promise<SubscriptionRequest> {
  return clientFetch<SubscriptionRequest>("/investor-operations/subscriptions", {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export async function submitRedemption(
  fundSlug: string,
  data: { investor_id: string; amount: string; notice_date?: string },
): Promise<RedemptionRequest> {
  return clientFetch<RedemptionRequest>("/investor-operations/redemptions", {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export async function kycDecision(
  fundSlug: string,
  requestId: string,
  data: { approved: boolean; decision_by: string; notes?: string },
): Promise<SubscriptionRequest> {
  return clientFetch<SubscriptionRequest>(
    `/investor-operations/subscriptions/${requestId}/kyc-decision`,
    { fundSlug, method: "POST", body: data },
  );
}

export async function opsReview(
  fundSlug: string,
  requestId: string,
  data: { approved: boolean; decision_by: string; notes?: string },
): Promise<SubscriptionRequest> {
  return clientFetch<SubscriptionRequest>(
    `/investor-operations/subscriptions/${requestId}/ops-review`,
    { fundSlug, method: "POST", body: data },
  );
}

export async function gpDecision(
  fundSlug: string,
  requestId: string,
  data: { approved: boolean; decision_by: string },
): Promise<SubscriptionRequest> {
  return clientFetch<SubscriptionRequest>(
    `/investor-operations/subscriptions/${requestId}/gp-decision`,
    { fundSlug, method: "POST", body: data },
  );
}

export async function confirmWire(
  fundSlug: string,
  requestId: string,
  data: { wire_reference: string },
): Promise<SubscriptionRequest> {
  return clientFetch<SubscriptionRequest>(
    `/investor-operations/subscriptions/${requestId}/confirm-wire`,
    { fundSlug, method: "POST", body: data },
  );
}

export async function cancelSubscription(
  fundSlug: string,
  requestId: string,
  data: { reason: string; cancelled_by: string },
): Promise<SubscriptionRequest> {
  return clientFetch<SubscriptionRequest>(
    `/investor-operations/subscriptions/${requestId}/cancel`,
    { fundSlug, method: "POST", body: data },
  );
}

export async function cancelRedemption(
  fundSlug: string,
  requestId: string,
  data: { reason: string; cancelled_by: string },
): Promise<RedemptionRequest> {
  return clientFetch<RedemptionRequest>(
    `/investor-operations/redemptions/${requestId}/cancel`,
    { fundSlug, method: "POST", body: data },
  );
}

export async function confirmPayment(
  fundSlug: string,
  requestId: string,
  data: { payment_reference: string },
): Promise<RedemptionRequest> {
  return clientFetch<RedemptionRequest>(
    `/investor-operations/redemptions/${requestId}/confirm-payment`,
    { fundSlug, method: "POST", body: data },
  );
}

export async function screenInvestorKYC(
  fundSlug: string,
  investorId: string,
  data: { name: string; entity_type?: string },
): Promise<InvestorKYC> {
  return clientFetch<InvestorKYC>(
    `/investor-operations/investors/${investorId}/kyc/screen`,
    { fundSlug, method: "POST", body: data },
  );
}
