import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { RuleDefinition, Violation } from "./types";

export type RemediationSuggestion = {
  violation_id: string;
  instrument_id: string;
  side: string;
  quantity: string;
  reason: string;
};

export function rulesQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["compliance-rules", fundSlug],
    queryFn: () => clientFetch<RuleDefinition[]>("/compliance/rules", { fundSlug }),
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
  return clientFetch<RuleDefinition>("/compliance/rules", {
    fundSlug,
    method: "POST",
    body,
  });
}

export async function updateRule(
  fundSlug: string,
  ruleId: string,
  body: Record<string, unknown>,
): Promise<RuleDefinition> {
  return clientFetch<RuleDefinition>(`/compliance/rules/${ruleId}`, {
    fundSlug,
    method: "PATCH",
    body,
  });
}

export function violationsQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["violations", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<Violation[]>(`/compliance/violations?portfolio_id=${portfolioId}`, { fundSlug }),
    staleTime: 60_000,
  });
}

export async function waiveViolation(
  fundSlug: string,
  violationId: string,
  data: { waived_by: string; reason: string },
): Promise<Violation> {
  return clientFetch<Violation>(`/compliance/violations/${violationId}/waive`, {
    fundSlug,
    method: "POST",
    body: data,
  });
}

export function remediationQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["remediation", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<RemediationSuggestion[]>(
        `/compliance/violations/remediation?portfolio_id=${portfolioId}`,
        { fundSlug },
      ),
    staleTime: 60_000,
  });
}

export interface ComplianceCheckResult {
  rule_id: string;
  rule_name: string;
  passed: boolean;
  severity: string;
  message: string;
  current_value: string | null;
  limit_value: string | null;
}

export interface ComplianceDecision {
  approved: boolean;
  results: ComplianceCheckResult[];
  blocked_by: string[];
}

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
  return clientFetch<ComplianceDecision>("/compliance/check", {
    fundSlug,
    method: "POST",
    body,
  });
}

export async function deleteRule(fundSlug: string, ruleId: string): Promise<void> {
  return clientFetch<void>(`/compliance/rules/${ruleId}`, {
    fundSlug,
    method: "DELETE",
  });
}
