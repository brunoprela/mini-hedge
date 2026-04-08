"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { createBlockAllocation } from "@/features/orders/api";
import type { CreateBlockAllocationRequest } from "@/features/orders/types";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

interface BlockAllocationDialogProps {
  onClose: () => void;
}

interface LegEntry {
  portfolio_id: string;
  target_pct: string;
}

export function BlockAllocationDialog({ onClose }: BlockAllocationDialogProps) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  const [instrumentId, setInstrumentId] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [totalQuantity, setTotalQuantity] = useState("");
  const [orderType, setOrderType] = useState<"market" | "limit">("market");
  const [limitPrice, setLimitPrice] = useState("");
  const [legs, setLegs] = useState<LegEntry[]>([{ portfolio_id: "", target_pct: "" }]);

  const mutation = useMutation({
    mutationFn: (request: CreateBlockAllocationRequest) => createBlockAllocation(fundSlug, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      toast.success("Block allocation created successfully");
      onClose();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to create block allocation");
    },
  });

  const legPctTotal = legs.reduce((sum, leg) => sum + (parseFloat(leg.target_pct) || 0), 0);
  const totalQty = parseFloat(totalQuantity) || 0;
  const pctMismatch = legPctTotal > 0 && Math.abs(legPctTotal - 100) > 0.01;

  function addLeg() {
    setLegs([...legs, { portfolio_id: "", target_pct: "" }]);
  }

  function removeLeg(index: number) {
    setLegs(legs.filter((_, i) => i !== index));
  }

  function updateLeg(index: number, field: keyof LegEntry, value: string) {
    setLegs(legs.map((leg, i) => (i === index ? { ...leg, [field]: value } : leg)));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (pctMismatch) {
      toast.error("Allocation percentages must sum to 100%");
      return;
    }

    const request: CreateBlockAllocationRequest = {
      instrument_id: instrumentId,
      side,
      total_quantity: totalQty,
      order_type: orderType,
      ...(orderType === "limit" ? { limit_price: parseFloat(limitPrice) } : {}),
      legs: legs.map((leg) => ({
        fund_slug: fundSlug,
        portfolio_id: leg.portfolio_id,
        target_pct: parseFloat(leg.target_pct) / 100,
      })),
    };

    mutation.mutate(request);
  }

  const canSubmit =
    instrumentId &&
    totalQty > 0 &&
    !pctMismatch &&
    legs.length > 0 &&
    legs.every((l) => l.portfolio_id && parseFloat(l.target_pct) > 0) &&
    (orderType !== "limit" || parseFloat(limitPrice) > 0) &&
    !mutation.isPending;

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: modal backdrop dismiss
    // biome-ignore lint/a11y/noStaticElementInteractions: modal backdrop dismiss
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      {/* biome-ignore lint/a11y/useKeyWithClickEvents: stops click propagation to backdrop */}
      {/* biome-ignore lint/a11y/noStaticElementInteractions: dialog container */}
      <div
        className="w-full max-w-lg rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Block Allocation</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {/* Instrument ID */}
          <div>
            <label htmlFor="block-instrument-id" className="mb-1 block text-sm font-medium">
              Instrument ID
            </label>
            <input
              id="block-instrument-id"
              type="text"
              value={instrumentId}
              onChange={(e) => setInstrumentId(e.target.value)}
              placeholder="e.g. AAPL"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            />
          </div>

          {/* Side */}
          <div>
            <span className="mb-1 block text-sm font-medium">Side</span>
            <div className="flex gap-1 rounded-md border border-[var(--border)] p-0.5">
              <button
                type="button"
                onClick={() => setSide("buy")}
                className={`flex-1 rounded px-3 py-1 text-sm font-medium transition-colors ${
                  side === "buy"
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Buy
              </button>
              <button
                type="button"
                onClick={() => setSide("sell")}
                className={`flex-1 rounded px-3 py-1 text-sm font-medium transition-colors ${
                  side === "sell"
                    ? "bg-[var(--destructive)] text-white"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Sell
              </button>
            </div>
          </div>

          {/* Total Quantity */}
          <div>
            <label htmlFor="block-total-quantity" className="mb-1 block text-sm font-medium">
              Total Quantity
            </label>
            <input
              id="block-total-quantity"
              type="number"
              value={totalQuantity}
              onChange={(e) => setTotalQuantity(e.target.value)}
              min="0"
              step="any"
              placeholder="0"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            />
          </div>

          {/* Order Type */}
          <div>
            <label htmlFor="block-order-type" className="mb-1 block text-sm font-medium">
              Order Type
            </label>
            <select
              id="block-order-type"
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as "market" | "limit")}
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </select>
          </div>

          {/* Limit Price */}
          {orderType === "limit" && (
            <div>
              <label htmlFor="block-limit-price" className="mb-1 block text-sm font-medium">
                Limit Price
              </label>
              <input
                id="block-limit-price"
                type="number"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                min="0"
                step="any"
                placeholder="0.00"
                className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              />
            </div>
          )}

          {/* Allocation Legs */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium">Allocation Legs</span>
              <button
                type="button"
                onClick={addLeg}
                className="text-sm text-[var(--primary)] hover:underline"
              >
                Add Portfolio
              </button>
            </div>
            <div className="space-y-2">
              {legs.map((leg, index) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: dynamic form rows
                <div key={index} className="flex items-center gap-2">
                  <select
                    value={leg.portfolio_id}
                    onChange={(e) => updateLeg(index, "portfolio_id", e.target.value)}
                    className="flex-1 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                  >
                    <option value="">Select portfolio</option>
                    {portfolios?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    value={leg.target_pct}
                    onChange={(e) => updateLeg(index, "target_pct", e.target.value)}
                    min="0"
                    max="100"
                    step="any"
                    placeholder="%"
                    className="w-28 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                  />
                  {legs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeLeg(index)}
                      className="text-sm text-[var(--destructive)] hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
            {pctMismatch && legPctTotal > 0 && (
              <p className="mt-1 text-xs text-[var(--destructive)]">
                Allocations sum to {legPctTotal.toFixed(1)}% (must be 100%)
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-[var(--border)] px-4 py-1.5 text-sm font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {mutation.isPending ? "Creating..." : "Create Allocation"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
