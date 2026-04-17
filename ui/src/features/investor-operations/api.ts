import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
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
  return queryOptions({
    queryKey: ["subscriptions", fundSlug, state ?? "all"],
    queryFn: async (): Promise<SubscriptionRequest[]> => {
      const { data, error } = await api.GET(
        "/api/v1/investor-operations/subscriptions",
        {
          params: { query: state ? { state } : {} },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 30_000,
  });
}

export function redemptionsQueryOptions(fundSlug: string, state?: string) {
  return queryOptions({
    queryKey: ["redemptions", fundSlug, state ?? "all"],
    queryFn: async (): Promise<RedemptionRequest[]> => {
      const { data, error } = await api.GET(
        "/api/v1/investor-operations/redemptions",
        {
          params: { query: state ? { state } : {} },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 30_000,
  });
}

export function queueSummaryQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["investor-ops-queue", fundSlug],
    queryFn: async (): Promise<QueueSummary> => {
      const { data, error } = await api.GET("/api/v1/investor-operations/queue", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      if (!data) throw new Error("Empty queue summary response");
      return data;
    },
    staleTime: 30_000,
  });
}

export function fundTermsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["fund-terms", fundSlug],
    queryFn: async (): Promise<FundTerms[]> => {
      const { data, error } = await api.GET(
        "/api/v1/investor-operations/fund-terms",
        {
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
//  Mutations
// ---------------------------------------------------------------------------

export async function submitSubscription(
  fundSlug: string,
  body: { investor_id: string; amount: string; share_class?: string },
): Promise<SubscriptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/subscriptions",
    {
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty subscription response");
  return data;
}

export async function submitRedemption(
  fundSlug: string,
  body: { investor_id: string; amount: string; notice_date?: string },
): Promise<RedemptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/redemptions",
    {
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty redemption response");
  return data;
}

export async function kycDecision(
  fundSlug: string,
  requestId: string,
  body: { approved: boolean; decision_by: string; notes?: string },
): Promise<SubscriptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/subscriptions/{request_id}/kyc-decision",
    {
      params: { path: { request_id: requestId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty KYC decision response");
  return data;
}

export async function opsReview(
  fundSlug: string,
  requestId: string,
  body: { approved: boolean; decision_by: string; notes?: string },
): Promise<SubscriptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/subscriptions/{request_id}/ops-review",
    {
      params: { path: { request_id: requestId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty ops review response");
  return data;
}

export async function gpDecision(
  fundSlug: string,
  requestId: string,
  body: { approved: boolean; decision_by: string },
): Promise<SubscriptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/subscriptions/{request_id}/gp-decision",
    {
      params: { path: { request_id: requestId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty GP decision response");
  return data;
}

export async function confirmWire(
  fundSlug: string,
  requestId: string,
  body: { wire_reference: string },
): Promise<SubscriptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/subscriptions/{request_id}/confirm-wire",
    {
      params: { path: { request_id: requestId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty confirm-wire response");
  return data;
}

export async function cancelSubscription(
  fundSlug: string,
  requestId: string,
  body: { reason: string; cancelled_by: string },
): Promise<SubscriptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/subscriptions/{request_id}/cancel",
    {
      params: { path: { request_id: requestId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty cancel response");
  return data;
}

export async function cancelRedemption(
  fundSlug: string,
  requestId: string,
  body: { reason: string; cancelled_by: string },
): Promise<RedemptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/redemptions/{request_id}/cancel",
    {
      params: { path: { request_id: requestId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty cancel response");
  return data;
}

export async function confirmPayment(
  fundSlug: string,
  requestId: string,
  body: { payment_reference: string },
): Promise<RedemptionRequest> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/redemptions/{request_id}/confirm-payment",
    {
      params: { path: { request_id: requestId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty confirm-payment response");
  return data;
}

export async function screenInvestorKYC(
  fundSlug: string,
  investorId: string,
  body: { name: string; entity_type?: string },
): Promise<InvestorKYC> {
  const { data, error } = await api.POST(
    "/api/v1/investor-operations/investors/{investor_id}/kyc/screen",
    {
      params: { path: { investor_id: investorId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty KYC screen response");
  return data;
}
