"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { runOptimization } from "../api";
import type { OptimizationResult } from "../types";

const OBJECTIVES = [
  { value: "min_variance", label: "Min Variance" },
  { value: "max_sharpe", label: "Max Sharpe" },
  { value: "risk_parity", label: "Risk Parity" },
] as const;

export function OptimizationPanel({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [objective, setObjective] = useState<string>("min_variance");
  const [result, setResult] = useState<OptimizationResult | null>(null);

  const mutation = useMutation({
    mutationFn: () => runOptimization(fundSlug, portfolioId, objective),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["alpha-optimizations"] });
      queryClient.invalidateQueries({ queryKey: ["alpha-intents"] });
      toast.success("Optimization complete");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const fmtPct = (v: string) => {
    const n = parseFloat(v);
    return `${n >= 0 ? "+" : ""}${(n * 100).toFixed(2)}%`;
  };

  const fmtCurrency = (v: string) => {
    const n = parseFloat(v);
    return n.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    });
  };

  return (
    <div className="space-y-6">
      {/* Objective Selector */}
      <div className="flex items-end gap-4">
        <div>
          <label htmlFor="objective" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Objective
          </label>
          <select
            id="objective"
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          >
            {OBJECTIVES.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-md bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90 disabled:opacity-50"
        >
          {mutation.isPending ? "Running..." : "Run Optimization"}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Results</h3>

          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">Expected Return</p>
              <p className="mt-1 font-mono text-lg font-semibold">
                {fmtPct(result.expected_return)}
              </p>
            </div>
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">Expected Risk</p>
              <p className="mt-1 font-mono text-lg font-semibold">{fmtPct(result.expected_risk)}</p>
            </div>
            {result.sharpe_ratio && (
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-[var(--muted-foreground)]">Sharpe Ratio</p>
                <p className="mt-1 font-mono text-lg font-semibold">
                  {parseFloat(result.sharpe_ratio).toFixed(3)}
                </p>
              </div>
            )}
          </div>

          {/* Weights Table */}
          {result.weights.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="pb-2 pr-4">Instrument</th>
                    <th className="pb-2 pr-4 text-right">Current Weight</th>
                    <th className="pb-2 pr-4 text-right">Target Weight</th>
                    <th className="pb-2 pr-4 text-right">Delta Weight</th>
                    <th className="pb-2 pr-4 text-right">Delta Shares</th>
                    <th className="pb-2 text-right">Delta Value</th>
                  </tr>
                </thead>
                <tbody>
                  {result.weights.map((w) => (
                    <tr key={w.instrument_id} className="border-b border-[var(--border)]">
                      <td className="py-2 pr-4 font-mono font-medium">{w.instrument_id}</td>
                      <td className="py-2 pr-4 text-right font-mono">{fmtPct(w.current_weight)}</td>
                      <td className="py-2 pr-4 text-right font-mono">{fmtPct(w.target_weight)}</td>
                      <td
                        className={`py-2 pr-4 text-right font-mono ${
                          parseFloat(w.delta_weight) >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--destructive)]"
                        }`}
                      >
                        {fmtPct(w.delta_weight)}
                      </td>
                      <td
                        className={`py-2 pr-4 text-right font-mono ${
                          parseFloat(w.delta_shares) >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--destructive)]"
                        }`}
                      >
                        {w.delta_shares}
                      </td>
                      <td
                        className={`py-2 text-right font-mono ${
                          parseFloat(w.delta_value) >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--destructive)]"
                        }`}
                      >
                        {fmtCurrency(w.delta_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
