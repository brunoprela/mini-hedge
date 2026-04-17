"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { ErrorState } from "@mini-hedge/ui";
import { TableSkeleton } from "@mini-hedge/ui";
import { api, fundHeaders } from "@/shared/lib/api-client";

function formatCurrency(value: string | number) {
  return Number(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function formatNavPerShare(value: string | number) {
  return Number(value).toFixed(4);
}

export default function NAVReviewPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");

  const enabled = !!fundSlug;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["nav", "history", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eod/nav/history", {
        params: { query: { period: "90d" } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    enabled,
  });

  const sorted = data
    ? [...data].sort(
        (a, b) =>
          new Date(b.business_date).getTime() -
          new Date(a.business_date).getTime(),
      )
    : [];

  const latest = sorted[0] ?? null;

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">NAV Review</h2>

      <div className="mb-6">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
          showPortfolio={false}
        />
      </div>

      {!fundSlug && (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund to view NAV history.
        </p>
      )}

      {fundSlug && isLoading && <TableSkeleton rows={6} columns={3} />}

      {fundSlug && isError && (
        <ErrorState message={error.message} onRetry={refetch} />
      )}

      {fundSlug && !isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-3">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Latest NAV
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latest ? formatCurrency(latest.nav) : "--"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Latest NAV/Share
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latest ? formatNavPerShare(latest.nav_per_share) : "--"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Period
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                90d
              </dd>
            </div>
          </dl>

          {/* History table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">NAV</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">NAV/Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {sorted.map((row) => (
                  <tr key={row.business_date} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm">{row.business_date}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{formatCurrency(row.nav)}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{formatNavPerShare(row.nav_per_share)}</td>
                  </tr>
                ))}
                {sorted.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                      No NAV history found for this period.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
