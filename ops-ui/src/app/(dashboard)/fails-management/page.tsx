"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/shared/components/error-state";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
import type { SettlementRecord } from "@/shared/types";

const fmt = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 });

export default function FailsManagementPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");

  const enabled = !!portfolioId;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["fails", portfolioId],
    queryFn: () =>
      apiFetch<SettlementRecord[]>(
        `cash/${portfolioId}/settlements?status=failed`,
      ),
    enabled,
  });

  const retrySettlement = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`cash/${portfolioId}/settlements/${id}/retry`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fails"] });
      toast.success("Settlement retry initiated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const rows = data ?? [];
  const totalValue = rows.reduce(
    (sum, r) => sum + Number(r.settlement_amount || "0"),
    0,
  );
  const oldestFail =
    rows.length > 0
      ? rows.reduce((oldest, r) =>
          r.settlement_date < oldest.settlement_date ? r : oldest,
        ).settlement_date
      : null;

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Fails Management</h2>

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
          Select a fund and portfolio to view failed settlements.
        </p>
      )}

      {portfolioId && isLoading && (
        <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
          Loading...
        </p>
      )}

      {portfolioId && isError && (
        <ErrorState message={error.message} onRetry={refetch} />
      )}

      {portfolioId && !isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-3">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Fails
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {rows.length}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Value
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {fmt(totalValue.toString())}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Oldest Fail
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {oldestFail ?? "—"}
              </dd>
            </div>
          </dl>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">ID</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Instrument</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Amount</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Currency</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Settle Date</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Trade Date</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {rows.map((row) => (
                  <tr key={row.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm font-mono" title={row.id}>
                      {row.id.slice(0, 8)}…
                    </td>
                    <td className="px-3 py-2 text-sm">{row.instrument_id}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {fmt(row.settlement_amount)}
                    </td>
                    <td className="px-3 py-2 text-sm">{row.currency}</td>
                    <td className="px-3 py-2 text-sm">{row.settlement_date}</td>
                    <td className="px-3 py-2 text-sm">{row.trade_date}</td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge label={row.status} variant="danger" />
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <button
                        type="button"
                        disabled={retrySettlement.isPending}
                        onClick={() => retrySettlement.mutate(row.id)}
                        className="flex items-center gap-1 rounded bg-[var(--primary)] px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                      >
                        {retrySettlement.isPending && (
                          <Loader2 size={12} className="animate-spin" />
                        )}
                        Retry
                      </button>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                      No failed settlements found.
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
