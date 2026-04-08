"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { processCorporateActions } from "../api";

interface Props {
  onClose: () => void;
}

export function ProcessActionsDialog({ onClose }: Props) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [portfolioId, setPortfolioId] = useState("");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));

  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  const mutation = useMutation({
    mutationFn: () =>
      processCorporateActions(fundSlug, {
        portfolio_id: portfolioId,
        start_date: startDate,
        end_date: endDate,
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["corporate-actions"] });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      toast.success(`Processed ${result.length} corporate action(s)`);
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const canSubmit = portfolioId && startDate && endDate && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Process Corporate Actions</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        {/* Portfolio */}
        <div className="mb-4">
          <label htmlFor="ca-portfolio" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Portfolio
          </label>
          <select
            id="ca-portfolio"
            value={portfolioId}
            onChange={(e) => setPortfolioId(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="">Select a portfolio</option>
            {portfolios?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Start Date */}
        <div className="mb-4">
          <label htmlFor="ca-start-date" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Start Date
          </label>
          <input
            id="ca-start-date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>

        {/* End Date */}
        <div className="mb-4">
          <label htmlFor="ca-end-date" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            End Date
          </label>
          <input
            id="ca-end-date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>

        {/* Actions */}
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
            className="flex-1 rounded-md bg-[var(--primary)] py-2 text-sm font-medium text-[var(--primary-foreground)] transition-colors hover:brightness-110 disabled:opacity-50"
          >
            {mutation.isPending ? "Processing..." : "Process Actions"}
          </button>
        </div>
      </div>
    </div>
  );
}
