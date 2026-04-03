import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { RuleDefinition, Violation } from "./types";

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
    refetchInterval: 30_000,
  });
}
