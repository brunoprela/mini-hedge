"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { runWhatIf } from "@/features/alpha/api";
import type { WhatIfResult } from "@/features/alpha/types";
import { instrumentSearchQueryOptions } from "@/features/instruments/api";
import { latestPriceQueryOptions } from "@/features/market-data/api";
import { createOrder } from "@/features/orders/api";
import type { OrderSummary } from "@/features/orders/types";
import { useFundContext } from "@/shared/hooks/use-fund-context";

interface TradeTicketProps {
  portfolioId: string;
  onClose: () => void;
}

export function TradeTicket({ portfolioId, onClose }: TradeTicketProps) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [instrumentId, setInstrumentId] = useState("");
  const [search, setSearch] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [rejectionDetail, setRejectionDetail] = useState<OrderSummary | null>(null);
  const [impact, setImpact] = useState<WhatIfResult | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [showImpact, setShowImpact] = useState(true);

  const { data: searchResults } = useQuery(instrumentSearchQueryOptions(fundSlug, search));

  const { data: latestPrice } = useQuery({
    ...latestPriceQueryOptions(fundSlug, instrumentId),
    enabled: instrumentId.length > 0,
  });

  const mutation = useMutation({
    mutationFn: () =>
      createOrder(fundSlug, {
        portfolio_id: portfolioId,
        instrument_id: instrumentId,
        side,
        order_type: "market",
        quantity,
        limit_price: price,
        time_in_force: "day",
      }),
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio-summary"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["exposure"] });

      if (order.state === "rejected") {
        setRejectionDetail(order);
        toast.error("Order rejected by compliance");
      } else {
        toast.success(`${side.toUpperCase()} ${quantity} ${instrumentId} — ${order.state}`);
        onClose();
      }
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    // Clear previous impact when inputs change
    if (!instrumentId || Number(quantity) <= 0 || Number(price) <= 0) {
      setImpact(null);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
      setImpactLoading(true);
      try {
        const result = await runWhatIf(fundSlug, portfolioId, {
          scenario_name: "trade-preview",
          trades: [{ instrument_id: instrumentId, side, quantity, price }],
        });
        setImpact(result);
      } catch {
        setImpact(null);
      } finally {
        setImpactLoading(false);
      }
    }, 500);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [instrumentId, quantity, price, side, fundSlug, portfolioId]);

  function selectInstrument(ticker: string) {
    setInstrumentId(ticker);
    setSearch("");
    setShowSearch(false);
  }

  const handleUseMarketPrice = () => {
    if (latestPrice) {
      setPrice(latestPrice.mid);
    }
  };

  const canSubmit =
    instrumentId && Number(quantity) > 0 && Number(price) > 0 && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">New Order</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        {/* Rejection detail */}
        {rejectionDetail && (
          <div className="mb-4 rounded-md border border-[var(--destructive)]/20 bg-[var(--destructive-muted)] p-3 text-sm text-[var(--destructive)]">
            <p className="font-medium">Compliance Rejected</p>
            {rejectionDetail.rejection_reason && (
              <p className="mt-1 text-xs">{rejectionDetail.rejection_reason}</p>
            )}
            {rejectionDetail.compliance_results && (
              <ul className="mt-2 space-y-1 text-xs">
                {(rejectionDetail.compliance_results as Record<string, unknown>[]).map((r, i) => (
                  <li
                    key={`result-${r.rule_id ?? i}`}
                    className={r.passed ? "text-[var(--success)]" : "text-[var(--destructive)]"}
                  >
                    {r.passed ? "\u2713" : "\u2717"} {String(r.rule_name)}: {String(r.message)}
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              onClick={() => setRejectionDetail(null)}
              className="mt-2 text-xs underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Side toggle */}
        <div className="mb-4 flex gap-2">
          <button
            type="button"
            onClick={() => setSide("buy")}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              side === "buy"
                ? "bg-[var(--success)] text-white"
                : "border border-[var(--border)] text-[var(--muted-foreground)]"
            }`}
          >
            Buy
          </button>
          <button
            type="button"
            onClick={() => setSide("sell")}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              side === "sell"
                ? "bg-[var(--destructive)] text-white"
                : "border border-[var(--border)] text-[var(--muted-foreground)]"
            }`}
          >
            Sell
          </button>
        </div>

        {/* Instrument search */}
        <div className="relative mb-4">
          <span className="mb-1 block text-sm text-[var(--muted-foreground)]">Instrument</span>
          {instrumentId ? (
            <div className="flex items-center gap-2">
              <span className="font-mono font-medium">{instrumentId}</span>
              <button
                type="button"
                onClick={() => {
                  setInstrumentId("");
                  setShowSearch(true);
                }}
                className="text-xs text-[var(--muted-foreground)] underline"
              >
                change
              </button>
            </div>
          ) : (
            <input
              type="text"
              placeholder="Search instruments..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setShowSearch(true);
              }}
              onFocus={() => setShowSearch(true)}
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
            />
          )}
          {showSearch && searchResults && searchResults.length > 0 && (
            <div className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-[var(--border)] bg-[var(--background)] shadow-lg">
              {searchResults.map((inst) => (
                <button
                  type="button"
                  key={inst.id}
                  onClick={() => selectInstrument(inst.ticker)}
                  className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-[var(--muted)]"
                >
                  <span className="font-mono font-medium">{inst.ticker}</span>
                  <span className="text-[var(--muted-foreground)]">{inst.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quantity */}
        <div className="mb-4">
          <label
            htmlFor="trade-quantity"
            className="mb-1 block text-sm text-[var(--muted-foreground)]"
          >
            Quantity
          </label>
          <input
            id="trade-quantity"
            type="number"
            min="0"
            step="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="0"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 font-mono text-sm"
          />
        </div>

        {/* Price */}
        <div className="mb-4">
          <div className="mb-1 flex items-center justify-between text-sm text-[var(--muted-foreground)]">
            <label htmlFor="trade-price">Price</label>
            {latestPrice && (
              <button type="button" onClick={handleUseMarketPrice} className="text-xs underline">
                Use mid ({latestPrice.mid})
              </button>
            )}
          </div>
          <input
            id="trade-price"
            type="number"
            min="0"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="0.00"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 font-mono text-sm"
          />
        </div>

        {/* Notional */}
        {Number(quantity) > 0 && Number(price) > 0 && (
          <p className="mb-4 text-sm text-[var(--muted-foreground)]">
            Notional:{" "}
            <span className="font-mono font-medium">
              $
              {(Number(quantity) * Number(price)).toLocaleString("en-US", {
                minimumFractionDigits: 2,
              })}
            </span>
          </p>
        )}

        {/* Impact Preview */}
        {(impact || impactLoading) && (
          <div className="mb-4 rounded-md border border-[var(--border)] bg-[var(--muted)] p-3">
            <button
              type="button"
              onClick={() => setShowImpact(!showImpact)}
              className="flex w-full items-center justify-between text-sm font-medium"
            >
              Impact Preview
              <span className="text-xs text-[var(--muted-foreground)]">
                {showImpact ? "▾" : "▸"}
              </span>
            </button>
            {showImpact &&
              (impactLoading ? (
                <p className="mt-2 text-xs text-[var(--muted-foreground)]">Calculating impact...</p>
              ) : impact ? (
                <div className="mt-2 space-y-1.5 text-sm">
                  <ImpactRow
                    label="NAV"
                    before={fmtUsd(impact.current_nav)}
                    after={fmtUsd(impact.proposed_nav)}
                    delta={impact.nav_change_pct}
                  />
                  {impact.current_var_95 && impact.proposed_var_95 && (
                    <ImpactRow
                      label="VaR 95%"
                      before={fmtUsd(impact.current_var_95)}
                      after={fmtUsd(impact.proposed_var_95)}
                    />
                  )}
                  {impact.compliance_issues.length > 0 && (
                    <div className="mt-2 rounded border border-[var(--destructive)]/20 bg-[var(--destructive-muted)] p-2">
                      <p className="text-xs font-medium text-[var(--destructive)]">
                        Compliance Warnings
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {impact.compliance_issues.map((issue) => (
                          <li key={issue} className="text-xs text-[var(--destructive)]">
                            ⚠ {issue}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : null)}
          </div>
        )}

        {/* Submit */}
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
            className={`flex-1 rounded-md py-2 text-sm font-medium text-white transition-colors ${
              side === "buy"
                ? "bg-[var(--success)] hover:brightness-110 disabled:opacity-50"
                : "bg-[var(--destructive)] hover:brightness-110 disabled:opacity-50"
            }`}
          >
            {mutation.isPending
              ? "Submitting..."
              : `${side === "buy" ? "Buy" : "Sell"} ${instrumentId || "..."}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function ImpactRow({
  label,
  before,
  after,
  delta,
}: {
  label: string;
  before: string;
  after: string;
  delta?: string;
}) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <div className="flex items-baseline gap-2 font-mono text-xs">
        <span className="text-[var(--muted-foreground)]">{before}</span>
        <span>→</span>
        <span className="font-medium">{after}</span>
        {delta && (
          <span
            className={
              parseFloat(delta) >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"
            }
          >
            ({parseFloat(delta) >= 0 ? "+" : ""}
            {parseFloat(delta).toFixed(2)}%)
          </span>
        )}
      </div>
    </div>
  );
}

function fmtUsd(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}
