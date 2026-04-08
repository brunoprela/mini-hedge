"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { openForward } from "../api";

const CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD"];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

interface OpenForwardDialogProps {
  portfolioId: string;
  onClose: () => void;
  prefill?: {
    base_currency?: string;
    quote_currency?: string;
    direction?: string;
    notional?: string;
    contract_rate?: string;
  };
}

export function OpenForwardDialog({ portfolioId, onClose, prefill }: OpenForwardDialogProps) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [baseCurrency, setBaseCurrency] = useState(prefill?.base_currency || "EUR");
  const [quoteCurrency, setQuoteCurrency] = useState(prefill?.quote_currency || "USD");
  const [direction, setDirection] = useState<"buy" | "sell">(
    (prefill?.direction as "buy" | "sell") || "buy",
  );
  const [notional, setNotional] = useState(prefill?.notional || "");
  const [contractRate, setContractRate] = useState(prefill?.contract_rate || "");
  const [spotAtInception, setSpotAtInception] = useState("");
  const [tradeDate, setTradeDate] = useState(todayISO());
  const [maturityDate, setMaturityDate] = useState("");
  const [counterparty, setCounterparty] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      openForward(fundSlug, {
        portfolio_id: portfolioId,
        base_currency: baseCurrency,
        quote_currency: quoteCurrency,
        direction,
        notional,
        contract_rate: contractRate,
        spot_at_inception: spotAtInception,
        trade_date: tradeDate,
        maturity_date: maturityDate,
        ...(counterparty ? { counterparty } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fx-forwards"] });
      queryClient.invalidateQueries({ queryKey: ["fx-hedging-summary"] });
      toast.success("Forward contract opened");
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to open forward");
    },
  });

  const canSubmit =
    baseCurrency &&
    quoteCurrency &&
    baseCurrency !== quoteCurrency &&
    notional &&
    contractRate &&
    spotAtInception &&
    maturityDate;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <h2 className="text-sm font-semibold">Open FX Forward</h2>
        <p className="mb-4 text-sm text-[var(--muted-foreground)]">
          Create a new FX forward contract.
        </p>

        <div className="space-y-3">
          {/* Currency pair */}
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                Base Currency
              </span>
              <select
                value={baseCurrency}
                onChange={(e) => setBaseCurrency(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                Quote Currency
              </span>
              <select
                value={quoteCurrency}
                onChange={(e) => setQuoteCurrency(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Direction toggle */}
          <div>
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
              Direction
            </span>
            <div className="flex gap-1 rounded-md border border-[var(--border)] p-0.5">
              <button
                type="button"
                onClick={() => setDirection("buy")}
                className={`flex-1 rounded px-3 py-1 text-sm font-medium transition-colors ${
                  direction === "buy"
                    ? "bg-emerald-400/20 text-emerald-400"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Buy
              </button>
              <button
                type="button"
                onClick={() => setDirection("sell")}
                className={`flex-1 rounded px-3 py-1 text-sm font-medium transition-colors ${
                  direction === "sell"
                    ? "bg-red-400/20 text-red-400"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Sell
              </button>
            </div>
          </div>

          {/* Notional */}
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
              Notional
            </span>
            <input
              type="number"
              value={notional}
              onChange={(e) => setNotional(e.target.value)}
              placeholder="1000000"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            />
          </label>

          {/* Rates */}
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                Contract Rate
              </span>
              <input
                type="number"
                step="0.0001"
                value={contractRate}
                onChange={(e) => setContractRate(e.target.value)}
                placeholder="1.0850"
                className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                Spot at Inception
              </span>
              <input
                type="number"
                step="0.0001"
                value={spotAtInception}
                onChange={(e) => setSpotAtInception(e.target.value)}
                placeholder="1.0800"
                className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              />
            </label>
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                Trade Date
              </span>
              <input
                type="date"
                value={tradeDate}
                onChange={(e) => setTradeDate(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
                Maturity Date
              </span>
              <input
                type="date"
                value={maturityDate}
                onChange={(e) => setMaturityDate(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              />
            </label>
          </div>

          {/* Counterparty */}
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">
              Counterparty (optional)
            </span>
            <input
              type="text"
              value={counterparty}
              onChange={(e) => setCounterparty(e.target.value)}
              placeholder="e.g. Goldman Sachs"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            />
          </label>
        </div>

        <div className="mt-6 flex justify-end gap-2">
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
            disabled={!canSubmit || mutation.isPending}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Opening..." : "Open Forward"}
          </button>
        </div>
      </div>
    </div>
  );
}
