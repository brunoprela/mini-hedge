"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { fxInterestRatesQueryOptions, setInterestRate } from "../api";

export function InterestRatesPanel() {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: rates, isLoading } = useQuery(fxInterestRatesQueryOptions(fundSlug));

  const [editingCurrency, setEditingCurrency] = useState<string | null>(null);
  const [editRate, setEditRate] = useState("");

  const rateMutation = useMutation({
    mutationFn: ({ currency, rate }: { currency: string; rate: number }) =>
      setInterestRate(fundSlug, currency, rate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fx-interest-rates"] });
      toast.success("Interest rate updated");
      setEditingCurrency(null);
      setEditRate("");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to update rate");
    },
  });

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading rates...</div>;
  }

  if (!rates || rates.length === 0) {
    return (
      <div className="rounded-md border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        No interest rate data available.
      </div>
    );
  }

  // Group by currency, show latest rate per currency
  const byCurrency = new Map<string, typeof rates>();
  for (const r of rates) {
    const existing = byCurrency.get(r.currency) ?? [];
    existing.push(r);
    byCurrency.set(r.currency, existing);
  }

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from(byCurrency.entries()).map(([ccy, ccyRates]) => {
        const sorted = ccyRates.sort((a, b) => a.tenor_days - b.tenor_days);
        const shortRate = sorted[0];
        const isEditing = editingCurrency === ccy;

        return (
          <div key={ccy} className="rounded-md border border-[var(--border)] p-3">
            <p className="text-sm font-semibold">{ccy}</p>
            {isEditing ? (
              <div className="mt-1">
                <input
                  type="number"
                  step="0.01"
                  value={editRate}
                  onChange={(e) => setEditRate(e.target.value)}
                  placeholder={(Number(shortRate.rate) * 100).toFixed(2)}
                  className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-sm tabular-nums"
                />
                <div className="mt-1.5 flex gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      if (!editRate) return;
                      rateMutation.mutate({ currency: ccy, rate: Number(editRate) / 100 });
                    }}
                    disabled={!editRate || rateMutation.isPending}
                    className="rounded px-2 py-0.5 text-xs font-medium text-emerald-400 hover:bg-emerald-400/10 disabled:opacity-50"
                  >
                    {rateMutation.isPending ? "..." : "Save"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingCurrency(null);
                      setEditRate("");
                    }}
                    className="rounded px-2 py-0.5 text-xs font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setEditingCurrency(ccy);
                  setEditRate((Number(shortRate.rate) * 100).toFixed(2));
                }}
                className="mt-1 block text-left hover:text-[var(--primary)]"
                title="Click to edit"
              >
                <span className="text-lg tabular-nums">
                  {(Number(shortRate.rate) * 100).toFixed(2)}%
                </span>
              </button>
            )}
            <p className="text-xs text-[var(--muted-foreground)]">{shortRate.tenor_days}d rate</p>
          </div>
        );
      })}
    </div>
  );
}
