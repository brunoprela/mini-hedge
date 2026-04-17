import { queryOptions } from "@tanstack/react-query";
import type { components } from "@mini-hedge/api-types";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { RuleDefinition, Violation } from "./types";

export type RemediationSuggestion = components["schemas"]["RemediationSuggestion"];

export function rulesQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["compliance-rules", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/compliance/rules", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
  });
}

export async function createRule(
  fundSlug: string,
  body: {
    name: string;
    rule_type: string;
    severity: string;
    parameters: Record<string, unknown>;
  },
): Promise<RuleDefinition> {
  const { data, error } = await api.POST("/api/v1/compliance/rules", {
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  if (!data) throw new Error("Empty create rule response");
  return data;
}

export async function updateRule(
  fundSlug: string,
  ruleId: string,
  body: Record<string, unknown>,
): Promise<RuleDefinition> {
  const { data, error } = await api.PATCH("/api/v1/compliance/rules/{rule_id}", {
    params: { path: { rule_id: ruleId } },
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  if (!data) throw new Error("Empty update rule response");
  return data;
}

export function violationsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["violations", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/compliance/violations", {
        params: { query: { portfolio_id: portfolioId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export async function waiveViolation(
  fundSlug: string,
  violationId: string,
  body: { waived_by: string; reason: string },
): Promise<Violation> {
  const { data, error } = await api.POST(
    "/api/v1/compliance/violations/{violation_id}/waive",
    {
      params: { path: { violation_id: violationId } },
      body: body as never,
      headers: fundHeaders(fundSlug),
    },
  );
  if (error) throw error;
  if (!data) throw new Error("Empty waive violation response");
  return data;
}

export function remediationQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["remediation", fundSlug, portfolioId],
    queryFn: async (): Promise<RemediationSuggestion[]> => {
      const { data, error } = await api.GET(
        "/api/v1/compliance/violations/remediation",
        {
          params: { query: { portfolio_id: portfolioId } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 60_000,
  });
}

export type ComplianceCheckResult = components["schemas"]["EvaluationResult"];
export type ComplianceDecision = components["schemas"]["ComplianceDecision"];

export async function checkTradeCompliance(
  fundSlug: string,
  body: {
    portfolio_id: string;
    instrument_id: string;
    side: string;
    quantity: string;
    price: string;
  },
): Promise<ComplianceDecision> {
  const { data, error } = await api.POST("/api/v1/compliance/check", {
    body: body as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  if (!data) throw new Error("Empty compliance check response");
  return data;
}

/**
 * Soft-delete a rule by deactivating it via PATCH. The backend exposes no
 * DELETE handler for compliance rules; deactivating preserves the audit
 * trail and matches the existing toggle-off behavior.
 */
export async function deleteRule(fundSlug: string, ruleId: string): Promise<void> {
  await updateRule(fundSlug, ruleId, { is_active: false });
}
