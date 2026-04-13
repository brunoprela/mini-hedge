"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/shared/components/error-state";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
import type { TrackedBreak, AgingSummary } from "@/shared/types";

const STATUS_VARIANT: Record<string, "warning" | "neutral" | "success" | "danger"> = {
  open: "warning",
  investigating: "neutral",
  resolved: "success",
  escalated: "danger",
};

export default function ReconciliationPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");

  const enabled = !!portfolioId;

  const {
    data: breaks,
    isLoading: breaksLoading,
    isError: breaksError,
    error: breaksErr,
    refetch: refetchBreaks,
  } = useQuery({
    queryKey: ["reconciliation", "breaks", portfolioId],
    queryFn: () =>
      apiFetch<TrackedBreak[]>(
        `reconciliation/portfolios/${portfolioId}/breaks?status=open`,
      ),
    enabled,
  });

  const {
    data: aging,
    isLoading: agingLoading,
    isError: agingError,
    error: agingErr,
    refetch: refetchAging,
  } = useQuery({
    queryKey: ["reconciliation", "aging", portfolioId],
    queryFn: () =>
      apiFetch<AgingSummary>(
        `reconciliation/portfolios/${portfolioId}/aging`,
      ),
    enabled,
  });

  const patchBreak = useMutation({
    mutationFn: ({
      breakId,
      status,
      resolution_note,
    }: {
      breakId: string;
      status: "investigating" | "resolved" | "escalated";
      resolution_note?: string;
    }) =>
      apiFetch(`reconciliation/breaks/${breakId}`, {
        method: "PATCH",
        body: JSON.stringify({ status, resolution_note }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["reconciliation", "breaks", portfolioId],
      });
      queryClient.invalidateQueries({
        queryKey: ["reconciliation", "aging", portfolioId],
      });
      toast.success("Break status updated");
    },
    onError: (err) => toast.error(err.message),
  });

  const isLoading = breaksLoading || agingLoading;
  const isError = breaksError || agingError;
  const errorMessage =
    breaksErr?.message ?? agingErr?.message ?? "Something went wrong";

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Reconciliation</h2>

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

      {portfolioId && isLoading && (
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      )}

      {portfolioId && isError && (
        <ErrorState
          message={errorMessage}
          onRetry={() => {
            refetchBreaks();
            refetchAging();
          }}
        />
      )}

      {portfolioId && !isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-3">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Open Breaks
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {breaks?.length ?? 0}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                SLA Breached
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {aging?.sla_breached_count ?? 0}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Oldest Break
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {aging?.oldest_break_hours != null
                  ? `${aging.oldest_break_hours.toFixed(1)}h`
                  : "--"}
              </dd>
            </div>
          </dl>

          {/* Breaks table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Instrument</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Break Type</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Internal Qty</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Broker Qty</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Diff</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Material?</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {breaks?.map((b) => (
                  <tr key={b.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm">{b.business_date}</td>
                    <td className="px-3 py-2 text-sm font-mono">{b.instrument_id ?? "--"}</td>
                    <td className="px-3 py-2 text-sm">{b.break_type}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{b.internal_quantity}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{b.broker_quantity}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">{b.difference}</td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={b.is_material ? "Yes" : "No"}
                        variant={b.is_material ? "danger" : "neutral"}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={b.status}
                        variant={STATUS_VARIANT[b.status] ?? "neutral"}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <div className="flex items-center gap-1">
                        {b.status === "open" && (
                          <button
                            type="button"
                            onClick={() =>
                              patchBreak.mutate({ breakId: b.id, status: "investigating" })
                            }
                            disabled={patchBreak.isPending}
                            className="rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
                          >
                            Investigate
                          </button>
                        )}
                        {(b.status === "open" || b.status === "investigating") && (
                          <button
                            type="button"
                            onClick={() =>
                              patchBreak.mutate({ breakId: b.id, status: "resolved" })
                            }
                            disabled={patchBreak.isPending}
                            className="rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
                          >
                            Resolve
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {breaks?.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                      No open breaks found.
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
