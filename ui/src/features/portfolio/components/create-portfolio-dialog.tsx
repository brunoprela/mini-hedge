"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { createPortfolio } from "../api";

interface Props {
  onClose: () => void;
}

export function CreatePortfolioDialog({ onClose }: Props) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState("");
  const [baseCurrency, setBaseCurrency] = useState("USD");

  const mutation = useMutation({
    mutationFn: () =>
      createPortfolio(fundSlug, {
        name,
        strategy: strategy || undefined,
        base_currency: baseCurrency,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      toast.success(`Portfolio "${name}" created`);
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const canSubmit = name.trim().length > 0 && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Create Portfolio</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        {/* Name */}
        <div className="mb-4">
          <label htmlFor="cp-name" className="block text-xs font-medium text-[var(--muted-foreground)] mb-1">
            Name
          </label>
          <input
            id="cp-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Portfolio name"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          />
        </div>

        {/* Strategy */}
        <div className="mb-4">
          <label htmlFor="cp-strategy" className="block text-xs font-medium text-[var(--muted-foreground)] mb-1">
            Strategy
          </label>
          <input
            id="cp-strategy"
            type="text"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            placeholder="e.g. Long/Short Equity"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          />
        </div>

        {/* Base Currency */}
        <div className="mb-4">
          <label htmlFor="cp-currency" className="block text-xs font-medium text-[var(--muted-foreground)] mb-1">
            Base Currency
          </label>
          <select
            id="cp-currency"
            value={baseCurrency}
            onChange={(e) => setBaseCurrency(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          >
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
            <option value="JPY">JPY</option>
            <option value="CHF">CHF</option>
          </select>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-[var(--border)] px-4 py-1.5 text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Creating..." : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
