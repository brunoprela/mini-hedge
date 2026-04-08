"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { investorsQueryOptions } from "@/features/investors/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { submitSubscription } from "../api";

interface Props {
  onClose: () => void;
}

export function SubmitSubscriptionDialog({ onClose }: Props) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [investorId, setInvestorId] = useState("");
  const [amount, setAmount] = useState("");
  const [shareClass, setShareClass] = useState("default");

  const { data: investors } = useQuery(investorsQueryOptions(fundSlug));

  const mutation = useMutation({
    mutationFn: () =>
      submitSubscription(fundSlug, {
        investor_id: investorId,
        amount,
        share_class: shareClass,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      queryClient.invalidateQueries({ queryKey: ["investor-ops-queue"] });
      toast.success("Subscription submitted");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const canSubmit = investorId && Number(amount) > 0 && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Submit Subscription</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        <div className="mb-4">
          <label
            htmlFor="sub-investor"
            className="mb-1 block text-sm text-[var(--muted-foreground)]"
          >
            Investor
          </label>
          <select
            id="sub-investor"
            value={investorId}
            onChange={(e) => setInvestorId(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="">Select investor...</option>
            {investors?.map((inv) => (
              <option key={inv.id} value={inv.id}>
                {inv.name}
              </option>
            ))}
          </select>
        </div>

        <div className="mb-4">
          <label htmlFor="sub-amount" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Amount
          </label>
          <input
            id="sub-amount"
            type="number"
            min="0"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 font-mono text-sm"
          />
        </div>

        <div className="mb-4">
          <label htmlFor="sub-class" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Share Class
          </label>
          <input
            id="sub-class"
            type="text"
            value={shareClass}
            onChange={(e) => setShareClass(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-md border border-[var(--border)] py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit}
            className="flex-1 rounded-md bg-[var(--success)] py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Submitting..." : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
}
