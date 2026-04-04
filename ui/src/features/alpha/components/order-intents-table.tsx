"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { approveIntent, cancelIntent, orderIntentsQueryOptions } from "../api";

export function OrderIntentsTable({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const { data: intents, isLoading } = useQuery(orderIntentsQueryOptions(fundSlug, portfolioId));

  const approveMutation = useMutation({
    mutationFn: (intentId: string) => approveIntent(fundSlug, portfolioId, intentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alpha-intents"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      toast.success("Intent approved");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (intentId: string) => cancelIntent(fundSlug, portfolioId, intentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alpha-intents"] });
      toast.success("Intent cancelled");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const fmtCurrency = (v: string) => {
    const n = parseFloat(v);
    return n.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    });
  };

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading order intents...</p>;
  }

  if (!intents || intents.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No pending order intents.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
            <th className="pb-2 pr-4">Instrument</th>
            <th className="pb-2 pr-4">Side</th>
            <th className="pb-2 pr-4 text-right">Quantity</th>
            <th className="pb-2 pr-4 text-right">Est. Value</th>
            <th className="pb-2 pr-4">Reason</th>
            <th className="pb-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {intents.map((intent) => (
            <tr key={intent.instrument_id} className="border-b border-[var(--border)]">
              <td className="py-2 pr-4 font-mono font-medium">{intent.instrument_id}</td>
              <td className="py-2 pr-4">
                <span
                  className={`text-sm font-medium ${
                    intent.side === "buy" ? "text-[var(--success)]" : "text-[var(--destructive)]"
                  }`}
                >
                  {intent.side.toUpperCase()}
                </span>
              </td>
              <td className="py-2 pr-4 text-right font-mono">{intent.quantity}</td>
              <td className="py-2 pr-4 text-right font-mono">
                {fmtCurrency(intent.estimated_value)}
              </td>
              <td className="py-2 pr-4 text-sm text-[var(--muted-foreground)]">{intent.reason}</td>
              <td className="py-2 text-right">
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => approveMutation.mutate(intent.instrument_id)}
                    disabled={approveMutation.isPending}
                    className="rounded-md bg-[var(--success)] px-3 py-1 text-xs font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    onClick={() => cancelMutation.mutate(intent.instrument_id)}
                    disabled={cancelMutation.isPending}
                    className="rounded-md border border-[var(--border)] px-3 py-1 text-xs font-medium transition-colors hover:bg-[var(--destructive-muted)] disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
