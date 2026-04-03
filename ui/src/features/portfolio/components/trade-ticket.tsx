"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
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
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <p className="font-medium">Compliance Rejected</p>
            {rejectionDetail.rejection_reason && (
              <p className="mt-1 text-xs">{rejectionDetail.rejection_reason}</p>
            )}
            {rejectionDetail.compliance_results && (
              <ul className="mt-2 space-y-1 text-xs">
                {(rejectionDetail.compliance_results as Record<string, unknown>[]).map((r, i) => (
                  <li
                    key={`result-${r.rule_id ?? i}`}
                    className={r.passed ? "text-green-700" : "text-red-700"}
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
                ? "bg-green-600 text-white"
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
                ? "bg-red-600 text-white"
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
                ? "bg-green-600 hover:bg-green-700 disabled:bg-green-600/50"
                : "bg-red-600 hover:bg-red-700 disabled:bg-red-600/50"
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
