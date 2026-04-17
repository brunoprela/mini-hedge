"use client";

import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { HBarChart } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { VaRResult } from "../types";

export function VaRContributions({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const [result, setResult] = useState<VaRResult | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/risk/{portfolio_id}/var", {
        params: { path: { portfolio_id: portfolioId } },
        body: { method: "historical", confidence: 0.95, horizon_days: 1 } as never,
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data as VaRResult;
    },
    onSuccess: (data) => setResult(data),
  });

  const chartItems = useMemo(() => {
    if (!result?.contributions || result.contributions.length === 0) return [];
    return result.contributions
      .map((c) => ({
        label: c.instrument_id,
        value: Number(c.component_var),
      }))
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, 15);
  }, [result]);

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          VaR Contribution by Position
        </p>
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-md border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)] disabled:opacity-50"
        >
          {mutation.isPending ? "Computing..." : result ? "Recompute" : "Compute VaR"}
        </button>
      </div>

      {!result && !mutation.isPending && null}

      {mutation.isError && (
        <p className="text-xs text-[var(--destructive)]">
          Failed: {(mutation.error as Error).message}
        </p>
      )}

      {result && (
        <div className="space-y-2">
          {/* Summary strip */}
          <div className="flex items-center gap-2 text-xs">
            <div>
              <span className="text-[var(--muted-foreground)]">
                VaR ({(result.confidence_level * 100).toFixed(0)}%):{" "}
              </span>
              <span className="font-mono font-semibold">
                $
                {Math.abs(Number(result.var_amount)).toLocaleString("en-US", {
                  maximumFractionDigits: 0,
                })}
              </span>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">ES: </span>
              <span className="font-mono font-semibold">
                $
                {Math.abs(Number(result.expected_shortfall)).toLocaleString("en-US", {
                  maximumFractionDigits: 0,
                })}
              </span>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">VaR %: </span>
              <span className="font-mono font-semibold">
                {(Number(result.var_pct) * 100).toFixed(2)}%
              </span>
            </div>
          </div>

          {/* Contribution chart */}
          {chartItems.length > 0 ? (
            <HBarChart
              items={chartItems}
              formatValue={(v) =>
                `$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
              }
            />
          ) : (
            <p className="text-xs text-[var(--muted-foreground)]">
              No position-level contributions available.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
