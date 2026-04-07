"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { brinsonFachlerQueryOptions } from "@/features/attribution/api";
import { cashBalancesQueryOptions } from "@/features/cash/api";
import { violationsQueryOptions } from "@/features/compliance/api";
import { eodHistoryQueryOptions } from "@/features/eod/api";
import { fxHedgingSummaryQueryOptions } from "@/features/fx-hedging/api";
import { capitalOverviewQueryOptions } from "@/features/investors/api";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { riskSnapshotQueryOptions } from "@/features/risk/api";
import { InfoTooltip } from "@/shared/components/table-controls";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";

export function DashboardSummaryCards() {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));
  const firstPortfolioId = portfolios?.[0]?.id;

  if (!firstPortfolioId) return null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {can(Permission.RISK_READ) && <RiskCard portfolioId={firstPortfolioId} />}
      {can(Permission.CASH_READ) && <CashCard portfolioId={firstPortfolioId} />}
      {can(Permission.ATTRIBUTION_READ) && <AttributionCard portfolioId={firstPortfolioId} />}
      {can(Permission.COMPLIANCE_READ) && <ComplianceCard portfolioId={firstPortfolioId} />}
      {can(Permission.CAPITAL_READ) && <InvestorCard />}
      {can(Permission.FX_HEDGING_READ) && <FXHedgingCard portfolioId={firstPortfolioId} />}
      {can(Permission.EOD_READ) && <EODCard />}
    </div>
  );
}

function RiskCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

  return (
    <SummaryCard
      title="Risk"
      href={`/${fundSlug}/risk`}
      items={
        data
          ? [
              {
                label: "VaR 95%",
                value: fmt(data.var_95_1d),
                info: "Maximum expected daily loss at 95% confidence",
              },
              {
                label: "VaR 99%",
                value: fmt(data.var_99_1d),
                info: "Maximum expected daily loss at 99% confidence",
              },
            ]
          : [{ label: "Status", value: "No snapshot" }]
      }
      accentColor="var(--accent-purple)"
      accentBg="var(--accent-purple-muted)"
    />
  );
}

function CashCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data } = useQuery(cashBalancesQueryOptions(fundSlug, portfolioId));

  const totalAvailable = data ? data.reduce((acc, b) => acc + Number(b.available_balance), 0) : 0;

  return (
    <SummaryCard
      title="Cash"
      href={`/${fundSlug}/cash`}
      items={[
        {
          label: "Available",
          value: fmt(String(totalAvailable)),
          info: "Total cash available for trading across all currencies",
        },
        {
          label: "Currencies",
          value: String(data?.length ?? 0),
          info: "Number of distinct currency balances held",
        },
      ]}
      accentColor="var(--accent-orange)"
      accentBg="var(--accent-orange-muted)"
    />
  );
}

function AttributionCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const end = new Date().toISOString().slice(0, 10);
  const start = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const { data } = useQuery(brinsonFachlerQueryOptions(fundSlug, portfolioId, start, end));

  return (
    <SummaryCard
      title="Attribution"
      href={`/${fundSlug}/attribution`}
      items={
        data
          ? [
              {
                label: "Active Return",
                value: pct(data.active_return),
                info: "Portfolio return minus benchmark return over 30 days",
              },
              {
                label: "Allocation",
                value: pct(data.total_allocation),
                info: "Return contribution from sector weight differences vs benchmark",
              },
            ]
          : [{ label: "Status", value: "Not calculated" }]
      }
      accentColor="var(--accent-cyan)"
      accentBg="var(--accent-cyan-muted)"
    />
  );
}

function ComplianceCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data } = useQuery(violationsQueryOptions(fundSlug, portfolioId));

  const activeCount = data?.filter((v) => !v.resolved_at).length ?? 0;

  return (
    <SummaryCard
      title="Compliance"
      href={`/${fundSlug}/compliance`}
      items={[
        {
          label: "Active Violations",
          value: String(activeCount),
          className: activeCount > 0 ? "text-[var(--destructive)]" : "text-[var(--success)]",
          info: "Number of unresolved compliance rule breaches",
        },
      ]}
      accentColor="var(--destructive)"
      accentBg="var(--destructive-muted)"
    />
  );
}

function FXHedgingCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data } = useQuery(fxHedgingSummaryQueryOptions(fundSlug, portfolioId));

  return (
    <SummaryCard
      title="FX Hedging"
      href={`/${fundSlug}/fx-hedging`}
      items={
        data
          ? [
              {
                label: "Open Forwards",
                value: String(data.total_open_forwards),
                info: "Number of active FX forward contracts",
              },
              {
                label: "Net MTM",
                value: fmt(data.net_mtm),
                info: "Net mark-to-market value of all open forwards",
              },
            ]
          : [{ label: "Status", value: "No forwards" }]
      }
      accentColor="var(--accent-cyan)"
      accentBg="var(--accent-cyan-muted)"
    />
  );
}

function EODCard() {
  const { fundSlug } = useFundContext();
  const { data: history } = useQuery(eodHistoryQueryOptions(fundSlug));

  const latest = history?.[0];

  return (
    <SummaryCard
      title="EOD & NAV"
      href={`/${fundSlug}/eod`}
      items={
        latest
          ? [
              {
                label: "Last Run",
                value: latest.business_date,
                info: "Most recent end-of-day processing date",
              },
              {
                label: "Status",
                value: latest.is_successful ? "Success" : "Failed",
                className: latest.is_successful
                  ? "text-[var(--success)]"
                  : "text-[var(--destructive)]",
                info: `${latest.steps_completed}/${latest.steps_total} steps completed`,
              },
            ]
          : [{ label: "Status", value: "No runs" }]
      }
      accentColor="var(--accent-orange)"
      accentBg="var(--accent-orange-muted)"
    />
  );
}

function InvestorCard() {
  const { fundSlug } = useFundContext();
  const { data } = useQuery(capitalOverviewQueryOptions(fundSlug));

  return (
    <SummaryCard
      title="Investors"
      href={`/${fundSlug}/investors`}
      items={
        data
          ? [
              {
                label: "Total AUM",
                value: fmt(data.total_aum),
                info: "Total assets under management across all investors",
              },
              {
                label: "Investors",
                value: String(data.total_investors),
                info: "Number of active investors in this fund",
              },
            ]
          : [{ label: "Status", value: "No data" }]
      }
      accentColor="var(--accent-green)"
      accentBg="var(--accent-green-muted)"
    />
  );
}

function SummaryCard({
  title,
  href,
  items,
  accentColor,
  accentBg,
}: {
  title: string;
  href: string;
  items: { label: string; value: string; className?: string; info?: string }[];
  accentColor: string;
  accentBg: string;
}) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:bg-[var(--card-hover)]"
    >
      <div className="mb-3 flex items-center gap-2">
        <div className="h-2 w-2 rounded-full" style={{ backgroundColor: accentColor }} />
        <h3 className="text-sm font-medium text-[var(--foreground-bright)]">{title}</h3>
      </div>
      <div className="space-y-2 rounded-lg p-3" style={{ backgroundColor: accentBg }}>
        {items.map((item) => (
          <div key={item.label} className="flex items-baseline justify-between">
            <span className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
              {item.label}
              {item.info && <InfoTooltip text={item.info} />}
            </span>
            <span className={`font-mono text-sm font-semibold ${item.className ?? ""}`}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </Link>
  );
}

function fmt(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function pct(v: string): string {
  const n = parseFloat(v) * 100;
  if (Number.isNaN(n)) return v;
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}
