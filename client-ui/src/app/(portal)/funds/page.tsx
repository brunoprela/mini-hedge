"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api";
import { ErrorState } from "@/shared/components/error-state";
import Link from "next/link";
import { useFunds } from "@/shared/components/fund-selector";
import type {
  FundCapitalOverview,
  CapitalAccountSummary,
  InvestorInfo,
} from "@/shared/types";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export default function FundsPage() {
  const { data: fundsPage, isLoading: fundsLoading, error: fundsError, refetch } = useFunds();
  const funds = fundsPage?.items ?? [];

  // Fetch overview + first investor's accounts for each fund
  const { data: fundData, isLoading: dataLoading, error: dataError } = useQuery({
    queryKey: ["my-funds-detail", funds.map((f) => f.slug)],
    queryFn: async () => {
      return Promise.all(
        funds.map(async (f) => {
          const [overview, investors] = await Promise.all([
            apiFetch<FundCapitalOverview>(`funds/${f.slug}/capital/overview`),
            apiFetch<InvestorInfo[]>(`funds/${f.slug}/capital/investors`),
          ]);
          let accounts: CapitalAccountSummary[] = [];
          if (investors.length > 0) {
            accounts = await apiFetch<CapitalAccountSummary[]>(
              `funds/${f.slug}/capital/investors/${investors[0].id}/accounts`,
            );
          }
          return { fund: f, overview, accounts };
        }),
      );
    },
    enabled: funds.length > 0,
  });

  const isLoading = fundsLoading || dataLoading;
  const error = fundsError || dataError;

  if (error) {
    return <ErrorState message={String(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">My Funds</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Funds where you hold capital accounts.
        </p>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Fund Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Share Class
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Shares Held
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Ending Capital
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Ownership %
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
            ) : !fundData || fundData.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                  No fund accounts found.
                </td>
              </tr>
            ) : (
              fundData.flatMap((fd) =>
                fd.accounts.length > 0
                  ? fd.accounts.map((acct) => (
                      <tr key={acct.id} className="hover:bg-[var(--table-row-hover)]">
                        <td className="px-4 py-3 font-medium text-[var(--foreground)]">
                          <Link href={`/funds/${fd.fund.slug}`} className="hover:underline text-[var(--primary)]">
                            {fd.fund.name}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-[var(--muted-foreground)]">
                          {acct.share_class}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {Number(acct.shares_held).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums font-medium">
                          {formatCurrency(Number(acct.ending_capital))}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {Number(acct.ownership_pct).toFixed(2)}%
                        </td>
                      </tr>
                    ))
                  : [
                      <tr key={fd.fund.slug} className="hover:bg-[var(--table-row-hover)]">
                        <td className="px-4 py-3 font-medium text-[var(--foreground)]">
                          <Link href={`/funds/${fd.fund.slug}`} className="hover:underline text-[var(--primary)]">
                            {fd.fund.name}
                          </Link>
                        </td>
                        <td
                          colSpan={4}
                          className="px-4 py-3 text-[var(--muted-foreground)] italic"
                        >
                          No capital accounts
                        </td>
                      </tr>,
                    ],
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
