"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { runWhatIf } from "../api";
import type { HypotheticalTrade, WhatIfResult } from "../types";

type TradeRow = HypotheticalTrade & { _key: string };

let nextTradeKey = 0;
function emptyTrade(): TradeRow {
  return {
    _key: `trade-${++nextTradeKey}`,
    instrument_id: "",
    side: "buy",
    quantity: "",
    price: "",
  };
}

export function WhatIfForm({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [scenarioName, setScenarioName] = useState("");
  const [trades, setTrades] = useState<TradeRow[]>([emptyTrade()]);
  const [result, setResult] = useState<WhatIfResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      runWhatIf(fundSlug, portfolioId, {
        scenario_name: scenarioName,
        trades: trades.map(({ _key, ...rest }) => rest),
      }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["alpha-scenarios"] });
      toast.success("What-If analysis complete");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  function updateTrade(index: number, field: keyof TradeRow, value: string) {
    setTrades((prev) => prev.map((t, i) => (i === index ? { ...t, [field]: value } : t)));
  }

  function removeTrade(index: number) {
    setTrades((prev) => prev.filter((_, i) => i !== index));
  }

  function addTrade() {
    setTrades((prev) => [...prev, emptyTrade()]);
  }

  const canSubmit =
    scenarioName.trim().length > 0 &&
    trades.length > 0 &&
    trades.every((t) => t.instrument_id && Number(t.quantity) > 0 && Number(t.price) > 0) &&
    !mutation.isPending;

  const fmtCurrency = (v: string) => {
    const n = parseFloat(v);
    return n.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    });
  };

  const fmtPct = (v: string) => {
    const n = parseFloat(v);
    return `${n >= 0 ? "+" : ""}${(n * 100).toFixed(2)}%`;
  };

  return (
    <div className="space-y-6">
      {/* Scenario Name */}
      <div>
        <label
          htmlFor="scenario-name"
          className="mb-1 block text-sm text-[var(--muted-foreground)]"
        >
          Scenario Name
        </label>
        <input
          id="scenario-name"
          type="text"
          value={scenarioName}
          onChange={(e) => setScenarioName(e.target.value)}
          placeholder="e.g. Add Tech Exposure"
          className="w-full max-w-md rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
        />
      </div>

      {/* Trades */}
      <div>
        <p className="mb-2 text-sm font-medium">Hypothetical Trades</p>
        <div className="space-y-2">
          {trades.map((trade, idx) => (
            <div key={trade._key} className="flex items-center gap-2">
              <input
                type="text"
                value={trade.instrument_id}
                onChange={(e) => updateTrade(idx, "instrument_id", e.target.value)}
                placeholder="Instrument ID"
                className="w-40 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
              />
              <select
                value={trade.side}
                onChange={(e) => updateTrade(idx, "side", e.target.value)}
                className="rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
              <input
                type="number"
                min="0"
                step="1"
                value={trade.quantity}
                onChange={(e) => updateTrade(idx, "quantity", e.target.value)}
                placeholder="Quantity"
                className="w-28 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 font-mono text-sm"
              />
              <input
                type="number"
                min="0"
                step="0.01"
                value={trade.price}
                onChange={(e) => updateTrade(idx, "price", e.target.value)}
                placeholder="Price"
                className="w-28 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 font-mono text-sm"
              />
              {trades.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeTrade(idx)}
                  className="text-sm text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
                >
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addTrade}
          className="mt-2 text-sm text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
        >
          + Add trade
        </button>
      </div>

      {/* Submit */}
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={!canSubmit}
        className="rounded-md bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90 disabled:opacity-50"
      >
        {mutation.isPending ? "Running..." : "Run What-If"}
      </button>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Results</h3>

          {/* NAV Summary */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">Current NAV</p>
              <p className="mt-1 font-mono text-lg font-semibold">
                {fmtCurrency(result.current_nav)}
              </p>
            </div>
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">Proposed NAV</p>
              <p className="mt-1 font-mono text-lg font-semibold">
                {fmtCurrency(result.proposed_nav)}
              </p>
            </div>
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="text-xs text-[var(--muted-foreground)]">NAV Change</p>
              <p
                className={`mt-1 font-mono text-lg font-semibold ${
                  parseFloat(result.nav_change) >= 0
                    ? "text-[var(--success)]"
                    : "text-[var(--destructive)]"
                }`}
              >
                {fmtCurrency(result.nav_change)} ({fmtPct(result.nav_change_pct)})
              </p>
            </div>
            {result.proposed_var_95 && (
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-[var(--muted-foreground)]">Proposed VaR 95</p>
                <p className="mt-1 font-mono text-lg font-semibold">
                  {fmtCurrency(result.proposed_var_95)}
                </p>
              </div>
            )}
          </div>

          {/* Compliance Issues */}
          {result.compliance_issues.length > 0 && (
            <div className="rounded-md border border-[var(--destructive)]/30 bg-[var(--destructive-muted)] p-3">
              <p className="text-sm font-medium text-[var(--destructive)]">Compliance Issues</p>
              <ul className="mt-1 space-y-1">
                {result.compliance_issues.map((issue) => (
                  <li key={issue} className="text-sm text-[var(--destructive)]">
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Position Impacts Table */}
          {result.positions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="pb-2 pr-4">Instrument</th>
                    <th className="pb-2 pr-4 text-right">Current Qty</th>
                    <th className="pb-2 pr-4 text-right">Proposed Qty</th>
                    <th className="pb-2 pr-4 text-right">Current Value</th>
                    <th className="pb-2 pr-4 text-right">Proposed Value</th>
                    <th className="pb-2 pr-4 text-right">Current Weight</th>
                    <th className="pb-2 text-right">Proposed Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {result.positions.map((pos) => (
                    <tr key={pos.instrument_id} className="border-b border-[var(--border)]">
                      <td className="py-2 pr-4 font-mono font-medium">{pos.instrument_id}</td>
                      <td className="py-2 pr-4 text-right font-mono">{pos.current_quantity}</td>
                      <td className="py-2 pr-4 text-right font-mono">{pos.proposed_quantity}</td>
                      <td className="py-2 pr-4 text-right font-mono">
                        {fmtCurrency(pos.current_value)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono">
                        {fmtCurrency(pos.proposed_value)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono">
                        {fmtPct(pos.current_weight)}
                      </td>
                      <td className="py-2 text-right font-mono">{fmtPct(pos.proposed_weight)}</td>
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
