"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { violationsQueryOptions } from "@/features/compliance/api";
import { eodHistoryQueryOptions } from "@/features/eod/api";
import { fxHedgingSummaryQueryOptions } from "@/features/fx-hedging/api";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type Severity = "critical" | "warning" | "info";

interface ActionItem {
  severity: Severity;
  description: string;
  href: string;
}

const severityColor: Record<Severity, string> = {
  critical: "var(--destructive)",
  warning: "var(--accent-orange)",
  info: "var(--accent-cyan)",
};

export function ActionItemsCard() {
  const { fundSlug } = useFundContext();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));
  const firstPortfolioId = portfolios?.[0]?.id;

  const { data: violations } = useQuery({
    ...violationsQueryOptions(fundSlug, firstPortfolioId!),
    enabled: !!firstPortfolioId,
  });

  const { data: eodHistory } = useQuery(eodHistoryQueryOptions(fundSlug));

  const { data: fxSummary } = useQuery({
    ...fxHedgingSummaryQueryOptions(fundSlug, firstPortfolioId!),
    enabled: !!firstPortfolioId,
  });

  const items: ActionItem[] = [];

  // Compliance violations
  const unresolvedCount = violations?.filter((v) => !v.resolved_at).length ?? 0;
  if (unresolvedCount > 0) {
    items.push({
      severity: "critical",
      description: `${unresolvedCount} compliance violation${unresolvedCount === 1 ? "" : "s"} need${unresolvedCount === 1 ? "s" : ""} resolution`,
      href: `/${fundSlug}/compliance`,
    });
  }

  // EOD checks
  const latestEOD = eodHistory?.[0];
  const today = new Date().toISOString().slice(0, 10);

  if (!latestEOD || latestEOD.business_date !== today) {
    items.push({
      severity: "warning",
      description: "EOD has not been run today",
      href: `/${fundSlug}/eod`,
    });
  }

  if (latestEOD && !latestEOD.is_successful) {
    items.push({
      severity: "critical",
      description: "Last EOD run failed",
      href: `/${fundSlug}/eod`,
    });
  }

  // FX forwards expiring soon
  const expiringCount = fxSummary?.expiring_within_5d ?? 0;
  if (expiringCount > 0) {
    items.push({
      severity: "warning",
      description: `${expiringCount} FX forward${expiringCount === 1 ? "" : "s"} expiring within 5 days`,
      href: `/${fundSlug}/fx-hedging`,
    });
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h3 className="mb-3 text-sm font-medium text-[var(--foreground-bright)]">Action Items</h3>

      {items.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg bg-[var(--accent-green-muted)] px-3 py-2.5">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            className="shrink-0"
          >
            <path
              d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.47 10.53 4.22 8.28l.72-.72L6.47 9.1l4.59-4.59.72.72-5.31 5.3Z"
              fill="var(--success)"
            />
          </svg>
          <span className="text-sm text-[var(--success)]">All clear — no action items</span>
        </div>
      ) : (
        <div className="space-y-1">
          {items.map((item) => (
            <Link
              key={item.description}
              href={item.href}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-[var(--card-hover)]"
            >
              <div
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: severityColor[item.severity] }}
              />
              <span className="flex-1 text-sm text-[var(--foreground)]">{item.description}</span>
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                className="shrink-0 text-[var(--muted-foreground)]"
              >
                <path
                  d="M6 3.5 10.5 8 6 12.5"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
