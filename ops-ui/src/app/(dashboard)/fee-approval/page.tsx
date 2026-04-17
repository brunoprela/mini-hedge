"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState, TableSkeleton } from "@mini-hedge/ui";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@mini-hedge/ui";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { FeeAccrualResponse } from "@/shared/types";

function fmtUSD(value: string): string {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return value;
  return num.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export default function FeeApprovalPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");

  const enabled = !!fundSlug;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["fee-approval", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/funds/{fund_slug}/fees/accruals",
        {
          params: { path: { fund_slug: fundSlug }, query: {} },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      // Filter client-side — the `status` query param isn't declared in the
      // OpenAPI spec; backend returns all accruals for the fund.
      return (data ?? []).filter((row) => row.status === "crystallized");
    },
    enabled,
  });

  // Optimistic fee approval: immediately drop the approved row from the
  // crystallized-only list; roll back on failure.
  const approveFee = useMutation({
    mutationFn: async (accrualId: string) => {
      const { data, error } = await api.POST(
        "/api/v1/funds/{fund_slug}/fees/approve",
        {
          params: { path: { fund_slug: fundSlug } },
          body: { accrual_ids: [accrualId] },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    onMutate: async (accrualId) => {
      const queryKey = ["fee-approval", fundSlug];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<FeeAccrualResponse[]>(queryKey);
      queryClient.setQueryData<FeeAccrualResponse[] | undefined>(
        queryKey,
        (old) => old?.filter((row) => row.id !== accrualId),
      );
      return { previous, queryKey };
    },
    onSuccess: () => {
      toast.success("Fee approved");
    },
    onError: (err: Error, _vars, context) => {
      if (context?.previous && context.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
      toast.error(err.message);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["fee-approval"] });
    },
  });

  const rows = data ?? [];
  const totalPending = rows.reduce(
    (sum, r) => sum + parseFloat(r.accrued_amount || "0"),
    0,
  );

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Fee Approval</h2>

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
          Select a fund to review crystallized fees awaiting approval.
        </p>
      )}

      {fundSlug && isLoading && <TableSkeleton rows={6} columns={7} />}

      {fundSlug && isError && (
        <ErrorState message={error.message} onRetry={refetch} />
      )}

      {fundSlug && !isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-2">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Pending Approvals
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {rows.length}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Amount Pending
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {fmtUSD(totalPending.toString())}
              </dd>
            </div>
          </dl>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fee Type</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Accrued Amount</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Cumulative</th>
                  <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">NAV Basis</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {rows.map((row) => (
                  <tr
                    key={`${row.accrual_date}-${row.fee_type}`}
                    className="transition-colors hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-2 text-sm">{row.accrual_date}</td>
                    <td className="px-3 py-2 text-sm">{row.fee_type}</td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {fmtUSD(row.accrued_amount)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {fmtUSD(row.cumulative_amount)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {fmtUSD(row.nav_basis)}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge label={row.status} variant="warning" />
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <button
                        type="button"
                        disabled={approveFee.isPending}
                        onClick={() => row.id && approveFee.mutate(row.id)}
                        className="flex items-center gap-1 rounded bg-[var(--primary)] px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                      >
                        {approveFee.isPending && (
                          <Loader2 size={12} className="animate-spin" />
                        )}
                        Approve
                      </button>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                      No crystallized fees awaiting approval.
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
