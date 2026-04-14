"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { apiFetch } from "@/shared/lib/api";
import { ErrorState } from "@/shared/components/error-state";
import { useFunds, FundSelector } from "@/shared/components/fund-selector";
import type { SubscriptionRequestSummary, RedemptionRequestSummary } from "@/shared/types";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

type ActivityRow = {
  id: string;
  date: string;
  type: "Subscription" | "Redemption";
  amount: number;
  shareClass: string;
  state: string;
  investorName?: string;
};

export default function ActivityPage() {
  const { data: fundsPage, isLoading: fundsLoading, error: fundsError, refetch } = useFunds();
  const funds = fundsPage?.items ?? [];
  const [selectedSlug, setSelectedSlug] = useState<string>("");
  const slug = selectedSlug || funds[0]?.slug || "";

  const {
    data: subscriptions,
    isLoading: subsLoading,
    error: subsError,
  } = useQuery({
    queryKey: ["activity-subs", slug],
    queryFn: () =>
      apiFetch<SubscriptionRequestSummary[]>(`investor-operations/subscriptions?fund_slug=${slug}`),
    enabled: !!slug,
  });

  const {
    data: redemptions,
    isLoading: redsLoading,
    error: redsError,
  } = useQuery({
    queryKey: ["activity-reds", slug],
    queryFn: () =>
      apiFetch<RedemptionRequestSummary[]>(`investor-operations/redemptions?fund_slug=${slug}`),
    enabled: !!slug,
  });

  const rows = useMemo<ActivityRow[]>(() => {
    const subRows: ActivityRow[] = (subscriptions ?? []).map((s) => ({
      id: s.id,
      date: s.submitted_at,
      type: "Subscription" as const,
      amount: Number(s.requested_amount),
      shareClass: s.share_class,
      state: s.state,
    }));
    const redRows: ActivityRow[] = (redemptions ?? []).map((r) => ({
      id: r.id,
      date: r.submitted_at,
      type: "Redemption" as const,
      amount: -Number(r.requested_amount),
      shareClass: "",
      state: r.state,
    }));
    return [...subRows, ...redRows].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
    );
  }, [subscriptions, redemptions]);

  const isLoading = fundsLoading || subsLoading || redsLoading;
  const error = fundsError || subsError || redsError;

  if (error) {
    return <ErrorState message={String(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">
            Capital Activity
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Subscription and redemption requests.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3.5 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            <Plus size={15} />
            Request Subscription
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3.5 py-2 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--muted)]"
          >
            Request Redemption
          </button>
        </div>
      </div>

      {/* Fund Selector */}
      {funds.length > 1 && (
        <div className="flex items-center gap-2">
          <label className="text-sm text-[var(--muted-foreground)]">Fund:</label>
          <FundSelector funds={funds} value={slug} onChange={setSelectedSlug} />
        </div>
      )}

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
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Share Class
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Amount
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Status
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
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                  No activity found.
                </td>
              </tr>
            ) : (
              rows.map((tx) => {
                const isPending =
                  tx.state === "pending_kyc" ||
                  tx.state === "pending_ops" ||
                  tx.state === "pending_gp" ||
                  tx.state === "pending";
                return (
                  <tr key={tx.id} className="hover:bg-[var(--table-row-hover)]">
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">
                      {new Date(tx.date).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-[var(--foreground)]">{tx.type}</td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">
                      {tx.shareClass || "--"}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span
                        className={
                          tx.amount >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"
                        }
                      >
                        {tx.amount >= 0 ? "+" : ""}
                        {formatCurrency(Math.abs(tx.amount))}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          isPending
                            ? "bg-[var(--warning-muted)] text-[var(--warning)]"
                            : tx.state === "rejected"
                              ? "bg-[var(--destructive)]/10 text-[var(--destructive)]"
                              : "bg-[var(--success-muted)] text-[var(--success)]"
                        }`}
                      >
                        {tx.state.replace(/_/g, " ")}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
