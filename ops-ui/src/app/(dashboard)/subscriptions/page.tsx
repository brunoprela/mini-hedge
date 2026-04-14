"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
import type { SubscriptionRequestSummary, SubscriptionState } from "@/shared/types";

const STATES: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Pending KYC", value: "pending_kyc" },
  { label: "KYC Approved", value: "kyc_approved" },
  { label: "Pending Ops Review", value: "pending_ops_review" },
  { label: "Pending GP Approval", value: "pending_gp_approval" },
  { label: "Approved", value: "approved" },
  { label: "Pending Wire", value: "pending_wire" },
  { label: "Wire Confirmed", value: "wire_confirmed" },
  { label: "Executed", value: "executed" },
  { label: "Cancelled", value: "cancelled" },
];

function badgeVariant(state: SubscriptionState): "success" | "warning" | "danger" | "neutral" {
  if (state === "kyc_approved" || state === "approved" || state === "wire_confirmed" || state === "executed") return "success";
  if (state === "rejected" || state === "cancelled") return "danger";
  if (typeof state === "string" && state.startsWith("pending_")) return "warning";
  return "neutral";
}

const TERMINAL_STATES = new Set(["executed", "cancelled", "rejected"]);

export default function SubscriptionsPage() {
  const queryClient = useQueryClient();
  const [stateFilter, setStateFilter] = useState("");

  const path = stateFilter
    ? `investor-operations/subscriptions?state=${stateFilter}`
    : "investor-operations/subscriptions";

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["subscriptions", stateFilter],
    queryFn: () => apiFetch<SubscriptionRequestSummary[]>(path),
  });

  const opsReview = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      apiFetch(`investor-operations/subscriptions/${id}/ops-review`, {
        method: "POST",
        body: JSON.stringify({ approved, decision_by: "ops-console" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      toast.success("Ops review submitted");
    },
    onError: (err) => toast.error(err.message),
  });

  const gpDecision = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      apiFetch(`investor-operations/subscriptions/${id}/gp-decision`, {
        method: "POST",
        body: JSON.stringify({ approved, decision_by: "ops-console" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      toast.success("GP decision submitted");
    },
    onError: (err) => toast.error(err.message),
  });

  const confirmWire = useMutation({
    mutationFn: ({ id, wire_reference }: { id: string; wire_reference: string }) =>
      apiFetch(`investor-operations/subscriptions/${id}/confirm-wire`, {
        method: "POST",
        body: JSON.stringify({ wire_reference, confirmed_by: "ops-console" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      toast.success("Wire confirmed");
    },
    onError: (err) => toast.error(err.message),
  });

  const cancelSub = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      apiFetch(`investor-operations/subscriptions/${id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason, cancelled_by: "ops-console" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      toast.success("Subscription cancelled");
    },
    onError: (err) => toast.error(err.message),
  });

  const items = data ?? [];
  const totalCount = items.length;
  const pendingReview = items.filter((s) => s.state === "pending_ops_review").length;
  const pendingGP = items.filter((s) => s.state === "pending_gp_approval").length;
  const pendingWire = items.filter((s) => s.state === "pending_wire" || s.state === "approved").length;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Subscription Workflow</h2>
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
        >
          {STATES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {/* KPI strip */}
      <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-4">
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Total Subscriptions</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{totalCount}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Pending Review</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{pendingReview}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Pending GP</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{pendingGP}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Pending Wire</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{pendingWire}</dd>
        </div>
      </dl>

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : isError ? (
        <p className="text-sm text-red-600">{(error as Error).message}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">No subscriptions found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border)]">
            <thead>
              <tr>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">ID</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Investor</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Share Class</th>
                <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Amount</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">State</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Submitted</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {items.map((sub) => (
                <tr key={sub.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                  <td className="px-3 py-2 font-mono text-xs">{sub.id.slice(0, 8)}</td>
                  <td className="px-3 py-2 text-sm">{sub.investor_id.slice(0, 8)}</td>
                  <td className="px-3 py-2 text-sm">{sub.share_class}</td>
                  <td className="px-3 py-2 text-sm text-right font-mono">
                    {Number(sub.requested_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge label={sub.state} variant={badgeVariant(sub.state)} />
                  </td>
                  <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">
                    {sub.submitted_at ? new Date(sub.submitted_at).toLocaleDateString() : "-"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      {sub.state === "pending_ops_review" && (
                        <>
                          <button
                            type="button"
                            onClick={() => opsReview.mutate({ id: sub.id, approved: true })}
                            disabled={opsReview.isPending}
                            className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => opsReview.mutate({ id: sub.id, approved: false })}
                            disabled={opsReview.isPending}
                            className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {sub.state === "pending_gp_approval" && (
                        <>
                          <button
                            type="button"
                            onClick={() => gpDecision.mutate({ id: sub.id, approved: true })}
                            disabled={gpDecision.isPending}
                            className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                          >
                            GP Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => gpDecision.mutate({ id: sub.id, approved: false })}
                            disabled={gpDecision.isPending}
                            className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                          >
                            GP Reject
                          </button>
                        </>
                      )}
                      {(sub.state === "approved" || sub.state === "pending_wire") && (
                        <button
                          type="button"
                          onClick={() => {
                            const ref = window.prompt("Enter wire reference:");
                            if (ref) confirmWire.mutate({ id: sub.id, wire_reference: ref });
                          }}
                          disabled={confirmWire.isPending}
                          className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                        >
                          Confirm Wire
                        </button>
                      )}
                      {!TERMINAL_STATES.has(sub.state) && (
                        <button
                          type="button"
                          onClick={() => {
                            const reason = window.prompt("Cancellation reason:");
                            if (reason) cancelSub.mutate({ id: sub.id, reason });
                          }}
                          disabled={cancelSub.isPending}
                          className="rounded border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
