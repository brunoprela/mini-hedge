import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { BrinsonFachlerResult, CumulativeAttribution, RiskBasedResult } from "./types";

export function brinsonFachlerQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["attribution", "brinson-fachler", fundSlug, portfolioId, start, end],
    queryFn: () =>
      clientFetch<BrinsonFachlerResult>(
        `/attribution/${portfolioId}/brinson-fachler?start=${start}&end=${end}`,
        { fundSlug },
      ),
    enabled: Boolean(portfolioId && start && end),
  });
}

export function riskBasedQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["attribution", "risk-based", fundSlug, portfolioId, start, end],
    queryFn: () =>
      clientFetch<RiskBasedResult>(
        `/attribution/${portfolioId}/risk-based?start=${start}&end=${end}`,
        { fundSlug },
      ),
    enabled: Boolean(portfolioId && start && end),
  });
}

export function cumulativeQueryOptions(
  fundSlug: string,
  portfolioId: string,
  start: string,
  end: string,
) {
  return queryOptions({
    queryKey: ["attribution", "cumulative", fundSlug, portfolioId, start, end],
    queryFn: () =>
      clientFetch<CumulativeAttribution>(
        `/attribution/${portfolioId}/cumulative?start=${start}&end=${end}`,
        { fundSlug },
      ),
    enabled: Boolean(portfolioId && start && end),
  });
}
