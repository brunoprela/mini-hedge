"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, TrendingUp } from "lucide-react";
import { apiFetch } from "@/shared/lib/api";
import { ErrorState } from "@/shared/components/error-state";
import { useFunds } from "@/shared/components/fund-selector";
import type {
  FundCapitalOverview,
  CapitalAccountSummary,
  InvestorInfo,
  CapitalTransaction,
} from "@/shared/types";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export default function DashboardPage() {
  const { data: fundsPage, isLoading: fundsLoading, error: fundsError, refetch } = useFunds();
  const funds = fundsPage?.items ?? [];

  // Fetch capital overview for each fund
  const {
    data: overviews,
    isLoading: overviewsLoading,
    error: overviewsError,
  } = useQuery({
    queryKey: ["dashboard-overviews", funds.map((f) => f.slug)],
    queryFn: () =>
      Promise.all(
        funds.map((f) =>
          apiFetch<FundCapitalOverview>(`capital/overview?fund_slug=${f.slug}`).then((ov) => ({
            fund: f,
            overview: ov,
          })),
        ),
      ),
    enabled: funds.length > 0,
  });

  // Fetch capital accounts for the first fund's first investor for recent activity
  const firstFundSlug = funds[0]?.slug;
  const { data: investors } = useQuery({
    queryKey: ["dashboard-investors", firstFundSlug],
    queryFn: () => apiFetch<InvestorInfo[]>(`capital/investors?fund_slug=${firstFundSlug}`),
    enabled: !!firstFundSlug,
  });

  const firstInvestorId = investors?.[0]?.id;

  const { data: accounts } = useQuery({
    queryKey: ["dashboard-accounts", firstFundSlug, firstInvestorId],
    queryFn: () =>
      apiFetch<CapitalAccountSummary[]>(
        `capital/investors/${firstInvestorId}/history?fund_slug=${firstFundSlug}`,
      ),
    enabled: !!firstFundSlug && !!firstInvestorId,
  });

  const { data: transactions } = useQuery({
    queryKey: ["dashboard-transactions", firstFundSlug, firstInvestorId],
    queryFn: () =>
      apiFetch<CapitalTransaction[]>(
        `capital/investors/${firstInvestorId}/transactions?fund_slug=${firstFundSlug}`,
      ),
    enabled: !!firstFundSlug && !!firstInvestorId,
  });

  const isLoading = fundsLoading || overviewsLoading;
  const error = fundsError || overviewsError;

  if (error) {
    return <ErrorState message={String(error)} onRetry={() => refetch()} />;
  }

  // Aggregate KPIs across all funds
  const totalValue = overviews?.reduce((sum, o) => sum + Number(o.overview.total_aum), 0) ?? 0;
  const totalFunds = funds.length;
  const totalInvestors =
    overviews?.reduce((sum, o) => sum + o.overview.total_investors, 0) ?? 0;

  // Build fund rows from accounts data
  const fundRows =
    overviews?.map((o) => ({
      slug: o.fund.slug,
      name: o.fund.name,
      currency: o.fund.base_currency,
      totalAum: Number(o.overview.total_aum),
      totalShares: Number(o.overview.total_shares_outstanding),
      investors: o.overview.total_investors,
    })) ?? [];

  // Recent transactions (last 5)
  const recentActivity = (transactions ?? []).slice(0, 5);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">Dashboard</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Welcome back. Here is your investment overview.
        </p>
      </div>

      {/* KPI Strip */}
      {isLoading ? (
        <div className="grid grid-cols-4 divide-x divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)]">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="p-5 animate-pulse">
              <div className="h-3 w-24 rounded bg-[var(--muted)] mb-2" />
              <div className="h-7 w-32 rounded bg-[var(--muted)]" />
            </div>
          ))}
        </div>
      ) : (
        <dl className="grid grid-cols-4 divide-x divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <div className="p-5">
            <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
              Total Investment Value
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
              {formatCurrency(totalValue)}
            </dd>
          </div>
          <div className="p-5">
            <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
              Total Funds
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
              {totalFunds}
            </dd>
          </div>
          <div className="p-5">
            <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
              Total Investors
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
              {totalInvestors}
            </dd>
          </div>
          <div className="p-5">
            <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
              Pending Activity
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
              {recentActivity.filter((tx) => !tx.notes?.toLowerCase().includes("settled")).length}
            </dd>
          </div>
        </dl>
      )}

      {/* My Funds Table */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-[var(--foreground-bright)]">My Funds</h2>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Fund Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Currency
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Total AUM
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Shares Outstanding
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Investors
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                    Loading...
                  </td>
                </tr>
              ) : fundRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                    No funds found.
                  </td>
                </tr>
              ) : (
                fundRows.map((fund) => (
                  <tr key={fund.slug} className="hover:bg-[var(--table-row-hover)]">
                    <td className="px-4 py-3 font-medium text-[var(--foreground)]">{fund.name}</td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">{fund.currency}</td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium">
                      {formatCurrency(fund.totalAum)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {Number(fund.totalShares).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{fund.investors}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent Activity */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-[var(--foreground-bright)]">
          Recent Activity
        </h2>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Date
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Type
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Amount
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Shares
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {recentActivity.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                    No recent activity.
                  </td>
                </tr>
              ) : (
                recentActivity.map((tx) => {
                  const amt = Number(tx.amount);
                  return (
                    <tr key={tx.id} className="hover:bg-[var(--table-row-hover)]">
                      <td className="px-4 py-3 text-[var(--muted-foreground)]">
                        {tx.business_date}
                      </td>
                      <td className="px-4 py-3 text-[var(--foreground)]">{tx.transaction_type}</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        <span
                          className={
                            amt >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"
                          }
                        >
                          {amt >= 0 ? "+" : ""}
                          {formatCurrency(amt)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-[var(--muted-foreground)]">
                        {Number(tx.shares) !== 0 ? Number(tx.shares).toLocaleString() : "--"}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
