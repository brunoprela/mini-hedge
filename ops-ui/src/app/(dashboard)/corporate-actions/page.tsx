"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/shared/components/error-state";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";

interface ProcessedCorporateAction {
  id: string;
  instrument_id: string;
  action_type: string;
  ex_date: string;
  record_date: string | null;
  pay_date: string | null;
  details: Record<string, unknown>;
  processed_at: string;
  status: string;
}

function statusVariant(status: string): "success" | "warning" | "danger" {
  switch (status) {
    case "processed":
      return "success";
    case "pending":
      return "warning";
    case "failed":
      return "danger";
    default:
      return "warning";
  }
}

export default function CorporateActionsPage() {
  const queryClient = useQueryClient();
  const [startDate, setStartDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [endDate, setEndDate] = useState(
    new Date().toISOString().slice(0, 10),
  );

  const actionsQuery = useQuery({
    queryKey: ["corporate-actions"],
    queryFn: () => apiFetch<ProcessedCorporateAction[]>("corporate-actions"),
  });

  const processActions = useMutation({
    mutationFn: () =>
      apiFetch("corporate-actions/process", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["corporate-actions"] });
      toast.success("Corporate actions processed");
    },
    onError: (err) => toast.error(err.message),
  });

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Corporate Actions</h2>

      {/* Action bar */}
      <div className="mb-6 flex flex-wrap items-end gap-3">
        <label className="block">
          <span className="block text-xs text-[var(--muted-foreground)] mb-1">Start Date</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
          />
        </label>
        <label className="block">
          <span className="block text-xs text-[var(--muted-foreground)] mb-1">End Date</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
          />
        </label>
        <button
          type="button"
          disabled={processActions.isPending}
          onClick={() => processActions.mutate()}
          className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
        >
          {processActions.isPending && <Loader2 size={14} className="animate-spin" />}
          Process Actions
        </button>
      </div>

      {/* Table */}
      {actionsQuery.isLoading ? (
        <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : actionsQuery.isError ? (
        <ErrorState
          message={actionsQuery.error.message}
          onRetry={() => actionsQuery.refetch()}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border)]">
            <thead>
              <tr>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Instrument</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Action Type</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Ex Date</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Record Date</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Pay Date</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Processed At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {actionsQuery.data?.map((row) => (
                <tr key={row.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                  <td className="px-3 py-2 text-sm font-mono">{row.instrument_id}</td>
                  <td className="px-3 py-2 text-sm capitalize">{row.action_type}</td>
                  <td className="px-3 py-2 text-sm">{row.ex_date}</td>
                  <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">{row.record_date ?? "—"}</td>
                  <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">{row.pay_date ?? "—"}</td>
                  <td className="px-3 py-2 text-sm">
                    <StatusBadge label={row.status} variant={statusVariant(row.status)} />
                  </td>
                  <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">{row.processed_at}</td>
                </tr>
              ))}
              {actionsQuery.data?.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                    No corporate actions found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
