"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { StatusBadge, TableSkeleton } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";
import type { RedemptionState } from "@/shared/types";

const STATES: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Pending Validation", value: "pending_validation" },
  { label: "Validated", value: "validated" },
  { label: "Queued for NAV", value: "queued_for_nav" },
  { label: "NAV Calculated", value: "nav_calculated" },
  { label: "Pending Payment", value: "pending_payment" },
  { label: "Payment Sent", value: "payment_sent" },
  { label: "Executed", value: "executed" },
  { label: "Gate Applied", value: "gate_applied" },
  { label: "Cancelled", value: "cancelled" },
  { label: "Validation Failed", value: "validation_failed" },
];

function badgeVariant(state: RedemptionState): "success" | "warning" | "danger" | "neutral" {
  if (state === "payment_sent" || state === "executed") return "success";
  if (state === "cancelled" || state === "validation_failed") return "danger";
  if (state === "gate_applied") return "warning";
  if (typeof state === "string" && state.startsWith("pending_")) return "warning";
  return "neutral";
}

const TERMINAL_STATES = new Set(["executed", "cancelled", "validation_failed"]);

export default function RedemptionsPage() {
  const queryClient = useQueryClient();
  const [stateFilter, setStateFilter] = useState("");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["redemptions", stateFilter],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/investor-operations/redemptions",
        {
          params: {
            query: stateFilter ? { state: stateFilter } : {},
          },
        },
      );
      if (error) throw error;
      return data;
    },
  });

  const validate = useMutation({
    mutationFn: async (id: string) => {
      const { data, error } = await api.POST(
        "/api/v1/investor-operations/redemptions/{request_id}/validate",
        {
          params: { path: { request_id: id } },
          body: { share_class: "default" },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["redemptions"] });
      toast.success("Redemption validated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const confirmPayment = useMutation({
    mutationFn: async ({
      id,
      payment_reference,
    }: {
      id: string;
      payment_reference: string;
    }) => {
      const { data, error } = await api.POST(
        "/api/v1/investor-operations/redemptions/{request_id}/confirm-payment",
        {
          params: { path: { request_id: id } },
          body: { payment_reference },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["redemptions"] });
      toast.success("Payment confirmed");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const cancelRedemption = useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }) => {
      const { data, error } = await api.POST(
        "/api/v1/investor-operations/redemptions/{request_id}/cancel",
        {
          params: { path: { request_id: id } },
          body: { reason, cancelled_by: "ops-console" },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["redemptions"] });
      toast.success("Redemption cancelled");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const items = data ?? [];
  const totalCount = items.length;
  const pendingValidation = items.filter((r) => r.state === "pending_validation").length;
  const pendingPayment = items.filter((r) => r.state === "pending_payment").length;
  const gateApplied = items.filter((r) => r.gate_applied).length;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Redemption Workflow</h2>
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
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Total Redemptions</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{totalCount}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Pending Validation</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{pendingValidation}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Pending Payment</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{pendingPayment}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Gate Applied</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{gateApplied}</dd>
        </div>
      </dl>

      {isLoading ? (
        <TableSkeleton rows={6} columns={5} />
      ) : isError ? (
        <p className="text-sm text-red-600">{(error as Error).message}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">No redemptions found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border)]">
            <thead>
              <tr>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">ID</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Investor</th>
                <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Amount</th>
                <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Approved Amt</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">State</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Notice Date</th>
                <th scope="col" className="px-3 py-2 text-center text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Gate</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {items.map((red) => (
                <tr key={red.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                  <td className="px-3 py-2 font-mono text-xs">{red.id.slice(0, 8)}</td>
                  <td className="px-3 py-2 text-sm">{red.investor_id.slice(0, 8)}</td>
                  <td className="px-3 py-2 text-sm text-right font-mono">
                    {Number(red.requested_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className="px-3 py-2 text-sm text-right font-mono">
                    {red.approved_amount != null
                      ? Number(red.approved_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                      : "-"}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge label={red.state} variant={badgeVariant(red.state)} />
                  </td>
                  <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">
                    {red.notice_date ?? "-"}
                  </td>
                  <td className="px-3 py-2 text-center text-sm">
                    {red.gate_applied ? `${red.gate_pct ?? 0}%` : "-"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      {red.state === "pending_validation" && (
                        <button
                          type="button"
                          onClick={() => validate.mutate(red.id)}
                          disabled={validate.isPending}
                          className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                        >
                          Validate
                        </button>
                      )}
                      {red.state === "pending_payment" && (
                        <button
                          type="button"
                          onClick={() => {
                            const ref = window.prompt("Enter payment reference:");
                            if (ref) confirmPayment.mutate({ id: red.id, payment_reference: ref });
                          }}
                          disabled={confirmPayment.isPending}
                          className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                        >
                          Confirm Payment
                        </button>
                      )}
                      {!TERMINAL_STATES.has(red.state) && (
                        <button
                          type="button"
                          onClick={() => {
                            const reason = window.prompt("Cancellation reason:");
                            if (reason) cancelRedemption.mutate({ id: red.id, reason });
                          }}
                          disabled={cancelRedemption.isPending}
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
