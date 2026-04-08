"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";
import {
  cancelSubscription,
  confirmWire,
  gpDecision,
  kycDecision,
  opsReview,
  queueSummaryQueryOptions,
  redemptionsQueryOptions,
  subscriptionsQueryOptions,
} from "../api";
import type { SubscriptionRequest } from "../types";
import { RedemptionStateBadge, SubscriptionStateBadge } from "./state-badge";
import { SubmitRedemptionDialog } from "./submit-redemption-dialog";
import { SubmitSubscriptionDialog } from "./submit-subscription-dialog";

function formatAmount(amount: string) {
  return Number(amount).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function formatDate(d: string | null) {
  if (!d) return "-";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

type Tab = "subscriptions" | "redemptions";

export function OperationsDashboard() {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("subscriptions");
  const [showSubmitSub, setShowSubmitSub] = useState(false);
  const [showSubmitRed, setShowSubmitRed] = useState(false);

  const { data: queue } = useQuery(queueSummaryQueryOptions(fundSlug));
  const { data: subscriptions } = useQuery(subscriptionsQueryOptions(fundSlug));
  const { data: redemptions } = useQuery(redemptionsQueryOptions(fundSlug));

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
    queryClient.invalidateQueries({ queryKey: ["redemptions"] });
    queryClient.invalidateQueries({ queryKey: ["investor-ops-queue"] });
  };

  // Subscription action mutations
  const kycMutation = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      kycDecision(fundSlug, id, { approved, decision_by: "ui-user" }),
    onSuccess: () => {
      invalidate();
      toast.success("KYC decision recorded");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const opsMutation = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      opsReview(fundSlug, id, { approved, decision_by: "ui-user" }),
    onSuccess: () => {
      invalidate();
      toast.success("Ops review recorded");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const gpMutation = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      gpDecision(fundSlug, id, { approved, decision_by: "ui-user" }),
    onSuccess: () => {
      invalidate();
      toast.success("GP decision recorded");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const wireMutation = useMutation({
    mutationFn: (id: string) => confirmWire(fundSlug, id, { wire_reference: `WIRE-${Date.now()}` }),
    onSuccess: () => {
      invalidate();
      toast.success("Wire confirmed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) =>
      cancelSubscription(fundSlug, id, { reason: "Cancelled via UI", cancelled_by: "ui-user" }),
    onSuccess: () => {
      invalidate();
      toast.success("Subscription cancelled");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function nextAction(sub: SubscriptionRequest) {
    if (!can(Permission.CAPITAL_WRITE)) return null;
    switch (sub.state) {
      case "pending_kyc":
        return (
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => kycMutation.mutate({ id: sub.id, approved: true })}
              className="rounded bg-[var(--success)] px-2 py-0.5 text-xs text-white"
            >
              Approve
            </button>
            <button
              type="button"
              onClick={() => kycMutation.mutate({ id: sub.id, approved: false })}
              className="rounded bg-[var(--destructive)] px-2 py-0.5 text-xs text-white"
            >
              Reject
            </button>
          </div>
        );
      case "kyc_approved":
        return (
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => opsMutation.mutate({ id: sub.id, approved: true })}
              className="rounded bg-[var(--success)] px-2 py-0.5 text-xs text-white"
            >
              Approve
            </button>
            <button
              type="button"
              onClick={() => opsMutation.mutate({ id: sub.id, approved: false })}
              className="rounded bg-[var(--destructive)] px-2 py-0.5 text-xs text-white"
            >
              Cancel
            </button>
          </div>
        );
      case "pending_ops_review":
        return (
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => opsMutation.mutate({ id: sub.id, approved: true })}
              className="rounded bg-[var(--success)] px-2 py-0.5 text-xs text-white"
            >
              Approve
            </button>
          </div>
        );
      case "pending_gp_approval":
        return (
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => gpMutation.mutate({ id: sub.id, approved: true })}
              className="rounded bg-[var(--success)] px-2 py-0.5 text-xs text-white"
            >
              Accept
            </button>
            <button
              type="button"
              onClick={() => gpMutation.mutate({ id: sub.id, approved: false })}
              className="rounded bg-[var(--destructive)] px-2 py-0.5 text-xs text-white"
            >
              Reject
            </button>
          </div>
        );
      case "approved":
        return (
          <button
            type="button"
            onClick={() => wireMutation.mutate(sub.id)}
            className="rounded bg-[var(--primary)] px-2 py-0.5 text-xs text-white"
          >
            Confirm Wire
          </button>
        );
      default:
        return null;
    }
  }

  const isTerminal = (s: string) =>
    ["executed", "cancelled", "kyc_rejected", "rejected"].includes(s);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Investor Operations</h1>
        {can(Permission.CAPITAL_WRITE) && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowSubmitSub(true)}
              className="rounded-md bg-[var(--success)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
            >
              + Subscription
            </button>
            <button
              type="button"
              onClick={() => setShowSubmitRed(true)}
              className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
            >
              + Redemption
            </button>
          </div>
        )}
      </div>

      {/* Queue summary cards */}
      {queue && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-md border border-[var(--border)] p-3">
            <div className="text-xs text-[var(--muted-foreground)]">Pending Subs</div>
            <div className="text-lg font-semibold">{queue.pending_subscriptions}</div>
            <div className="text-xs font-mono text-[var(--muted-foreground)]">
              {formatAmount(queue.total_subscription_amount)}
            </div>
          </div>
          <div className="rounded-md border border-[var(--border)] p-3">
            <div className="text-xs text-[var(--muted-foreground)]">Pending Reds</div>
            <div className="text-lg font-semibold">{queue.pending_redemptions}</div>
            <div className="text-xs font-mono text-[var(--muted-foreground)]">
              {formatAmount(queue.total_redemption_amount)}
            </div>
          </div>
          <div className="rounded-md border border-[var(--border)] p-3">
            <div className="text-xs text-[var(--muted-foreground)]">Next Dealing Date</div>
            <div className="text-lg font-semibold">{queue.next_dealing_date ?? "-"}</div>
          </div>
          <div className="rounded-md border border-[var(--border)] p-3">
            <div className="text-xs text-[var(--muted-foreground)]">Net Flow</div>
            <div className="text-lg font-semibold font-mono">
              {formatAmount(
                String(
                  Number(queue.total_subscription_amount) - Number(queue.total_redemption_amount),
                ),
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        <button
          type="button"
          onClick={() => setTab("subscriptions")}
          className={`px-3 py-1.5 text-xs font-medium border-b-2 -mb-px ${tab === "subscriptions" ? "border-[var(--primary)] text-[var(--foreground)]" : "border-transparent text-[var(--muted-foreground)]"}`}
        >
          Subscriptions ({subscriptions?.length ?? 0})
        </button>
        <button
          type="button"
          onClick={() => setTab("redemptions")}
          className={`px-3 py-1.5 text-xs font-medium border-b-2 -mb-px ${tab === "redemptions" ? "border-[var(--primary)] text-[var(--foreground)]" : "border-transparent text-[var(--muted-foreground)]"}`}
        >
          Redemptions ({redemptions?.length ?? 0})
        </button>
      </div>

      {/* Subscription table */}
      {tab === "subscriptions" && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="px-2 py-1.5 font-medium">ID</th>
                <th className="px-2 py-1.5 font-medium">Investor</th>
                <th className="px-2 py-1.5 font-medium">Amount</th>
                <th className="px-2 py-1.5 font-medium">State</th>
                <th className="px-2 py-1.5 font-medium">Submitted</th>
                <th className="px-2 py-1.5 font-medium">Dealing Date</th>
                <th className="px-2 py-1.5 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {subscriptions?.map((sub) => (
                <tr
                  key={sub.id}
                  className="border-b border-[var(--border)] hover:bg-[var(--muted)]/30"
                >
                  <td className="px-2 py-1.5 font-mono">{sub.id.slice(0, 8)}</td>
                  <td className="px-2 py-1.5 font-mono">{sub.investor_id.slice(0, 8)}</td>
                  <td className="px-2 py-1.5 font-mono">{formatAmount(sub.requested_amount)}</td>
                  <td className="px-2 py-1.5">
                    <SubscriptionStateBadge state={sub.state} />
                  </td>
                  <td className="px-2 py-1.5">{formatDate(sub.submitted_at)}</td>
                  <td className="px-2 py-1.5">{sub.dealing_date ?? "-"}</td>
                  <td className="px-2 py-1.5">
                    <div className="flex items-center gap-1">
                      {nextAction(sub)}
                      {!isTerminal(sub.state) && can(Permission.CAPITAL_WRITE) && (
                        <button
                          type="button"
                          onClick={() => cancelMutation.mutate(sub.id)}
                          className="rounded bg-[var(--muted)] px-2 py-0.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--destructive)] hover:text-white"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {(!subscriptions || subscriptions.length === 0) && (
                <tr>
                  <td colSpan={7} className="px-2 py-6 text-center text-[var(--muted-foreground)]">
                    No pending subscriptions
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Redemption table */}
      {tab === "redemptions" && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="px-2 py-1.5 font-medium">ID</th>
                <th className="px-2 py-1.5 font-medium">Investor</th>
                <th className="px-2 py-1.5 font-medium">Amount</th>
                <th className="px-2 py-1.5 font-medium">Approved</th>
                <th className="px-2 py-1.5 font-medium">State</th>
                <th className="px-2 py-1.5 font-medium">Notice Date</th>
                <th className="px-2 py-1.5 font-medium">Dealing Date</th>
              </tr>
            </thead>
            <tbody>
              {redemptions?.map((red) => (
                <tr
                  key={red.id}
                  className="border-b border-[var(--border)] hover:bg-[var(--muted)]/30"
                >
                  <td className="px-2 py-1.5 font-mono">{red.id.slice(0, 8)}</td>
                  <td className="px-2 py-1.5 font-mono">{red.investor_id.slice(0, 8)}</td>
                  <td className="px-2 py-1.5 font-mono">{formatAmount(red.requested_amount)}</td>
                  <td className="px-2 py-1.5 font-mono">
                    {red.approved_amount ? formatAmount(red.approved_amount) : "-"}
                  </td>
                  <td className="px-2 py-1.5">
                    <RedemptionStateBadge state={red.state} />
                  </td>
                  <td className="px-2 py-1.5">{red.notice_date}</td>
                  <td className="px-2 py-1.5">{red.dealing_date ?? "-"}</td>
                </tr>
              ))}
              {(!redemptions || redemptions.length === 0) && (
                <tr>
                  <td colSpan={7} className="px-2 py-6 text-center text-[var(--muted-foreground)]">
                    No pending redemptions
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Dialogs */}
      {showSubmitSub && <SubmitSubscriptionDialog onClose={() => setShowSubmitSub(false)} />}
      {showSubmitRed && <SubmitRedemptionDialog onClose={() => setShowSubmitRed(false)} />}
    </div>
  );
}
