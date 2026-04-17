"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { ErrorState } from "@mini-hedge/ui";
import { StatusBadge } from "@mini-hedge/ui";
import { TableSkeleton } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";

const SLA_VARIANT: Record<string, "success" | "warning" | "danger"> = {
  within_sla: "success",
  warning: "warning",
  breached: "danger",
};

export default function TradeReconPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");

  const enabled = !!portfolioId;

  const {
    data: latest,
    isLoading: latestLoading,
    isError: latestError,
    error: latestErr,
    refetch: refetchLatest,
  } = useQuery({
    queryKey: ["trade-recon", "latest", portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/reconciliation/portfolios/{portfolio_id}/latest",
        { params: { path: { portfolio_id: portfolioId } } },
      );
      if (error) throw error;
      return data;
    },
    enabled,
  });

  const {
    data: history,
    isLoading: historyLoading,
    isError: historyError,
    error: historyErr,
    refetch: refetchHistory,
  } = useQuery({
    queryKey: ["trade-recon", "history", portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/reconciliation/portfolios/{portfolio_id}/history",
        {
          params: {
            path: { portfolio_id: portfolioId },
            query: { limit: 20 },
          },
        },
      );
      if (error) throw error;
      return data;
    },
    enabled,
  });

  const {
    data: slaBreaks,
    isLoading: slaLoading,
    isError: slaError,
    error: slaErr,
    refetch: refetchSla,
  } = useQuery({
    queryKey: ["trade-recon", "sla", portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/reconciliation/portfolios/{portfolio_id}/sla-status",
        { params: { path: { portfolio_id: portfolioId } } },
      );
      if (error) throw error;
      return data;
    },
    enabled,
  });

  const isLoading = latestLoading || historyLoading || slaLoading;
  const isError = latestError || historyError || slaError;
  const errorMessage =
    latestErr?.message ?? historyErr?.message ?? slaErr?.message ?? "Something went wrong";

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Trade Reconciliation</h2>

      <div className="mb-6">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
        />
      </div>

      {!portfolioId && (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund and portfolio to view reconciliation data.
        </p>
      )}

      {portfolioId && isLoading && <TableSkeleton rows={6} columns={5} />}

      {portfolioId && isError && (
        <ErrorState
          message={errorMessage}
          onRetry={() => {
            refetchLatest();
            refetchHistory();
            refetchSla();
          }}
        />
      )}

      {portfolioId && !isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-4">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Positions
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latest?.total_positions ?? "--"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Matched
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latest?.matched_positions ?? "--"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Breaks
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latest?.break_count ?? "--"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Clean?
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latest ? (latest.is_clean ? "Yes" : "No") : "--"}
              </dd>
            </div>
          </dl>

          {/* SLA Status table */}
          <h3 className="mb-3 text-sm font-semibold text-[var(--muted-foreground)]">SLA Status</h3>
          <div className="mb-6 overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Break ID</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Instrument</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Break Type</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">SLA Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {slaBreaks?.map((item) => (
                  <tr key={item.tracked_break.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm font-mono">{item.tracked_break.id.slice(0, 8)}</td>
                    <td className="px-3 py-2 text-sm font-mono">{item.tracked_break.instrument_id ?? "--"}</td>
                    <td className="px-3 py-2 text-sm">{item.tracked_break.break_type}</td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge label={item.tracked_break.status} variant="neutral" />
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={item.sla_status}
                        variant={SLA_VARIANT[item.sla_status] ?? "neutral"}
                      />
                    </td>
                  </tr>
                ))}
                {slaBreaks?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                      No SLA breaks found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* History table */}
          <h3 className="mb-3 text-sm font-semibold text-[var(--muted-foreground)]">History</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Total Positions</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Matched</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Breaks</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Clean?</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Reconciled At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {history?.map((row) => (
                  <tr key={`${row.portfolio_id}-${row.business_date}`} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm">{row.business_date}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{row.total_positions}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{row.matched_positions}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{row.break_count}</td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={row.is_clean ? "Yes" : "No"}
                        variant={row.is_clean ? "success" : "danger"}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">
                      {row.reconciled_at
                        ? new Date(row.reconciled_at).toLocaleString()
                        : "--"}
                    </td>
                  </tr>
                ))}
                {history?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                      No reconciliation history found.
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
