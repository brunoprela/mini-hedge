"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { investorsQueryOptions } from "@/features/investors/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { submitRedemption } from "../api";

interface Props {
  onClose: () => void;
}

export function SubmitRedemptionDialog({ onClose }: Props) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [investorId, setInvestorId] = useState("");
  const [amount, setAmount] = useState("");
  const [noticeDate, setNoticeDate] = useState(() => new Date().toISOString().slice(0, 10));

  const { data: investors } = useQuery(investorsQueryOptions(fundSlug));

  const mutation = useMutation({
    mutationFn: () =>
      submitRedemption(fundSlug, {
        investor_id: investorId,
        amount,
        notice_date: noticeDate,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["redemptions"] });
      queryClient.invalidateQueries({ queryKey: ["investor-ops-queue"] });
      toast.success("Redemption submitted");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const canSubmit = investorId && Number(amount) > 0 && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Submit Redemption</h2>
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
            htmlFor="red-investor"
            className="mb-1 block text-sm text-[var(--muted-foreground)]"
          >
            Investor
          </label>
          <select
            id="red-investor"
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
          <label htmlFor="red-amount" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Amount
          </label>
          <input
            id="red-amount"
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
          <label htmlFor="red-date" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Notice Date
          </label>
          <input
            id="red-date"
            type="date"
            value={noticeDate}
            onChange={(e) => setNoticeDate(e.target.value)}
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
            className="flex-1 rounded-md bg-[var(--primary)] py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Submitting..." : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
}
