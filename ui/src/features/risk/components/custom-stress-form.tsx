"use client";

import { useMutation } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { runCustomStressTest } from "../api";
import type { StressTestResult } from "../types";

interface ShockRow {
  factor: string;
  value: string;
}

function emptyShock(): ShockRow {
  return { factor: "", value: "" };
}

function fmtCurrency(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmtPct(v: string) {
  return `${parseFloat(v).toFixed(2)}%`;
}

export function CustomStressForm({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [shocks, setShocks] = useState<ShockRow[]>([emptyShock()]);
  const [result, setResult] = useState<StressTestResult | null>(null);

  const mutation = useMutation({
    mutationFn: (data: { name: string; shocks: Record<string, number>; description?: string }) =>
      runCustomStressTest(fundSlug, portfolioId, data),
    onSuccess: (data) => {
      setResult(data);
      toast.success("Custom stress test completed");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to run stress test");
    },
  });

  const addShock = () => setShocks((prev) => [...prev, emptyShock()]);

  const removeShock = (index: number) =>
    setShocks((prev) => prev.filter((_, i) => i !== index));

  const updateShock = (index: number, field: keyof ShockRow, value: string) =>
    setShocks((prev) => prev.map((s, i) => (i === index ? { ...s, [field]: value } : s)));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const validShocks = shocks.filter((s) => s.factor.trim() && s.value.trim());
    if (!name.trim() || validShocks.length === 0) return;

    const shocksDict: Record<string, number> = {};
    for (const s of validShocks) {
      shocksDict[s.factor.trim()] = parseFloat(s.value);
    }

    mutation.mutate({
      name: name.trim(),
      shocks: shocksDict,
      description: description.trim() || undefined,
    });
  };

  const pnl = result ? parseFloat(result.total_pnl_impact) : 0;

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm text-[var(--muted-foreground)]">
              Scenario Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Equity crash"
              required
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-[var(--muted-foreground)]">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)]"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm text-[var(--muted-foreground)]">Shocks</label>
          <div className="space-y-2">
            {shocks.map((shock, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="text"
                  value={shock.factor}
                  onChange={(e) => updateShock(i, "factor", e.target.value)}
                  placeholder="Factor (e.g. SPX)"
                  className="w-40 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)]"
                />
                <input
                  type="number"
                  step="any"
                  value={shock.value}
                  onChange={(e) => updateShock(i, "value", e.target.value)}
                  placeholder="Shock (e.g. -10)"
                  className="w-32 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm font-mono outline-none focus:border-[var(--ring)]"
                />
                <button
                  type="button"
                  onClick={() => removeShock(i)}
                  disabled={shocks.length === 1}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-30"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addShock}
            className="mt-2 inline-flex items-center gap-1 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Shock
          </button>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-[var(--primary)] px-4 text-sm font-medium text-[var(--primary-foreground)] transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {mutation.isPending ? "Running..." : "Run Stress Test"}
          </button>
        </div>
      </form>

      {result && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
          <div className="flex items-baseline justify-between">
            <h4 className="text-sm font-semibold">{result.scenario_name}</h4>
            <div className="flex gap-4 text-sm">
              <span className={`font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}>
                PnL: {fmtCurrency(result.total_pnl_impact)}
              </span>
              <span className={`font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}>
                {fmtPct(result.total_pct_change)}
              </span>
            </div>
          </div>

          {result.position_impacts.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
                    <th className="px-4 py-2 text-left font-medium text-[var(--muted-foreground)]">
                      Instrument
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                      Current
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                      Stressed
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                      PnL Impact
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
                      % Change
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.position_impacts.map((impact) => {
                    const impactPnl = parseFloat(impact.pnl_impact);
                    return (
                      <tr
                        key={impact.instrument_id}
                        className="border-b border-[var(--table-border)] last:border-0"
                      >
                        <td className="px-4 py-2 font-medium">{impact.instrument_id}</td>
                        <td className="px-4 py-2 text-right font-mono">
                          {fmtCurrency(impact.current_value)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono">
                          {fmtCurrency(impact.stressed_value)}
                        </td>
                        <td
                          className={`px-4 py-2 text-right font-mono ${impactPnl < 0 ? "text-[var(--destructive)]" : ""}`}
                        >
                          {fmtCurrency(impact.pnl_impact)}
                        </td>
                        <td
                          className={`px-4 py-2 text-right font-mono ${impactPnl < 0 ? "text-[var(--destructive)]" : ""}`}
                        >
                          {fmtPct(impact.pct_change)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
