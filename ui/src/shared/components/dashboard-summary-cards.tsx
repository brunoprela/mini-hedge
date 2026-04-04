"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { brinsonFachlerQueryOptions } from "@/features/attribution/api";
import { cashBalancesQueryOptions } from "@/features/cash/api";
import { violationsQueryOptions } from "@/features/compliance/api";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { riskSnapshotQueryOptions } from "@/features/risk/api";
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
              { label: "VaR 95%", value: fmt(data.var_95_1d) },
              { label: "VaR 99%", value: fmt(data.var_99_1d) },
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
        { label: "Available", value: fmt(String(totalAvailable)) },
        { label: "Currencies", value: String(data?.length ?? 0) },
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
              { label: "Active Return", value: pct(data.active_return) },
              { label: "Allocation", value: pct(data.total_allocation) },
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
        },
      ]}
      accentColor="var(--destructive)"
      accentBg="var(--destructive-muted)"
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
  items: { label: string; value: string; className?: string }[];
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
            <span className="text-xs text-[var(--muted-foreground)]">{item.label}</span>
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
