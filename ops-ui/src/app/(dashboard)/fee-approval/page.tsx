"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/shared/components/error-state";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
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
    queryFn: () =>
      apiFetch<FeeAccrualResponse[]>(
        `funds/${fundSlug}/fees/accruals?status=crystallized`,
      ),
    enabled,
  });

  const approveFee = useMutation({
    mutationFn: (accrualId: string) =>
      apiFetch(`funds/${fundSlug}/fees/approve`, {
        method: "POST",
        body: JSON.stringify({ accrual_ids: [accrualId] }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fee-approval"] });
      toast.success("Fee approved");
    },
    onError: (err: Error) => toast.error(err.message),
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

      {fundSlug && isLoading && (
        <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
          Loading...
        </p>
      )}

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
