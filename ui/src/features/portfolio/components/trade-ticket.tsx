"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { runWhatIf } from "@/features/alpha/api";
import type { WhatIfResult } from "@/features/alpha/types";
import {
  checkTradeCompliance,
  type ComplianceDecision,
} from "@/features/compliance/api";
import { instrumentSearchQueryOptions } from "@/features/instruments/api";
import { latestPriceQueryOptions } from "@/features/market-data/api";
import { createAlgoOrder, createOrder } from "@/features/orders/api";
import type { AlgoType, OrderSummary } from "@/features/orders/types";
import { useFundContext } from "@/shared/hooks/use-fund-context";

interface TradeTicketProps {
  portfolioId: string;
  onClose: () => void;
  defaults?: { instrument?: string; side?: string; quantity?: string };
}

export function TradeTicket({ portfolioId, onClose, defaults }: TradeTicketProps) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [side, setSide] = useState<"buy" | "sell">(
    defaults?.side === "sell" ? "sell" : "buy",
  );
  const [instrumentId, setInstrumentId] = useState(defaults?.instrument ?? "");
  const [search, setSearch] = useState("");
  const [quantity, setQuantity] = useState(defaults?.quantity ?? "");
  const [price, setPrice] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [rejectionDetail, setRejectionDetail] = useState<OrderSummary | null>(null);
  const [impact, setImpact] = useState<WhatIfResult | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [showImpact, setShowImpact] = useState(true);

  // Compliance pre-check
  const [complianceCheck, setComplianceCheck] = useState<ComplianceDecision | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);

  // Algo order state
  const [useAlgo, setUseAlgo] = useState(false);
  const [algoType, setAlgoType] = useState<AlgoType>("twap");
  const [algoDuration, setAlgoDuration] = useState("3600");
  const [algoSlices, setAlgoSlices] = useState("100");
  const [algoVisibleQty, setAlgoVisibleQty] = useState("");

  const { data: searchResults } = useQuery(instrumentSearchQueryOptions(fundSlug, search));

  const { data: latestPrice } = useQuery({
    ...latestPriceQueryOptions(fundSlug, instrumentId),
    enabled: instrumentId.length > 0,
  });

  const mutation = useMutation({
    mutationFn: () => {
      if (useAlgo) {
        return createAlgoOrder(fundSlug, {
          portfolio_id: portfolioId,
          instrument_id: instrumentId,
          side,
          order_type: "limit",
          quantity,
          limit_price: price,
          time_in_force: "day",
          algo_type: algoType,
          algo_params: {
            duration_seconds: parseInt(algoDuration, 10) || 3600,
            num_slices: parseInt(algoSlices, 10) || 100,
            ...(algoType === "iceberg" && algoVisibleQty
              ? { visible_quantity: algoVisibleQty }
              : {}),
          },
        });
      }
      return createOrder(fundSlug, {
        portfolio_id: portfolioId,
        instrument_id: instrumentId,
        side,
        order_type: "market",
        quantity,
        limit_price: price,
        time_in_force: "day",
      });
    },
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

  // Debounced compliance pre-check + impact preview
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    if (!instrumentId || Number(quantity) <= 0 || Number(price) <= 0) {
      setImpact(null);
      setComplianceCheck(null);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
      // Run compliance check and impact in parallel
      setImpactLoading(true);
      setComplianceLoading(true);

      const [impactResult, complianceResult] = await Promise.allSettled([
        runWhatIf(fundSlug, portfolioId, {
          scenario_name: "trade-preview",
          trades: [{ instrument_id: instrumentId, side, quantity, price }],
        }),
        checkTradeCompliance(fundSlug, {
          portfolio_id: portfolioId,
          instrument_id: instrumentId,
          side,
          quantity,
          price,
        }),
      ]);

      setImpact(impactResult.status === "fulfilled" ? impactResult.value : null);
      setImpactLoading(false);
      setComplianceCheck(complianceResult.status === "fulfilled" ? complianceResult.value : null);
      setComplianceLoading(false);
    }, 600);

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

  const hasComplianceBlock =
    complianceCheck && !complianceCheck.approved && complianceCheck.blocked_by.length > 0;

  const canSubmit =
    instrumentId && Number(quantity) > 0 && Number(price) > 0 && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="flex w-full max-w-lg flex-col rounded-lg border border-[var(--border)] bg-[var(--background)] shadow-lg" style={{ maxHeight: "90vh" }}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
          <h2 className="text-lg font-semibold">New Order</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
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

          {/* Quantity + Price side by side */}
          <div className="mb-4 grid grid-cols-2 gap-3">
            <div>
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
            <div>
              <div className="mb-1 flex items-center justify-between text-sm text-[var(--muted-foreground)]">
                <label htmlFor="trade-price">Price</label>
                {latestPrice && (
                  <button type="button" onClick={handleUseMarketPrice} className="text-[10px] underline">
                    Mid: {latestPrice.mid}
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

          {/* Algo toggle */}
          <div className="mb-4">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={useAlgo}
                onChange={(e) => setUseAlgo(e.target.checked)}
                className="h-4 w-4 rounded border-[var(--border)]"
              />
              <span className="text-[var(--muted-foreground)]">Algo execution</span>
            </label>
          </div>

          {/* Algo params */}
          {useAlgo && (
            <div className="mb-4 space-y-3 rounded-md border border-[var(--border)] bg-[var(--muted)] p-3">
              <div>
                <span className="mb-1.5 block text-xs font-medium text-[var(--muted-foreground)]">
                  Algorithm
                </span>
                <div className="flex gap-1.5">
                  {(["twap", "vwap", "iceberg"] as const).map((t) => (
                    <button
                      type="button"
                      key={t}
                      onClick={() => setAlgoType(t)}
                      className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                        algoType === t
                          ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                          : "border border-[var(--border)] bg-[var(--background)] text-[var(--muted-foreground)]"
                      }`}
                    >
                      {t.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {algoType !== "iceberg" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label
                      htmlFor="algo-duration"
                      className="mb-1 block text-xs text-[var(--muted-foreground)]"
                    >
                      Duration (seconds)
                    </label>
                    <input
                      id="algo-duration"
                      type="number"
                      min="60"
                      step="60"
                      value={algoDuration}
                      onChange={(e) => setAlgoDuration(e.target.value)}
                      className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="algo-slices"
                      className="mb-1 block text-xs text-[var(--muted-foreground)]"
                    >
                      Slices
                    </label>
                    <input
                      id="algo-slices"
                      type="number"
                      min="2"
                      step="1"
                      value={algoSlices}
                      onChange={(e) => setAlgoSlices(e.target.value)}
                      className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 font-mono text-sm"
                    />
                  </div>
                </div>
              )}

              {algoType === "iceberg" && (
                <div>
                  <label
                    htmlFor="algo-visible"
                    className="mb-1 block text-xs text-[var(--muted-foreground)]"
                  >
                    Visible quantity (leave empty for auto)
                  </label>
                  <input
                    id="algo-visible"
                    type="number"
                    min="1"
                    step="1"
                    value={algoVisibleQty}
                    onChange={(e) => setAlgoVisibleQty(e.target.value)}
                    placeholder="Auto (total / 10)"
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 font-mono text-sm"
                  />
                </div>
              )}

              <p className="text-[10px] text-[var(--muted-foreground)]">
                {algoType === "twap" && "Splits order evenly across the time window."}
                {algoType === "vwap" && "Splits order proportional to historical volume."}
                {algoType === "iceberg" && "Shows only the visible quantity; replenishes on fill."}
              </p>
            </div>
          )}

          {/* ─── Compliance Pre-Check Results (Broadridge-style) ─── */}
          {(complianceCheck || complianceLoading) && (
            <div className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--muted)] p-3">
              <div className="mb-2 flex items-center gap-2">
                {complianceLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                    <span className="text-xs font-medium text-[var(--muted-foreground)]">
                      Running compliance checks...
                    </span>
                  </>
                ) : complianceCheck?.approved ? (
                  <>
                    <ShieldCheck className="h-4 w-4 text-[var(--success)]" />
                    <span className="text-xs font-medium text-[var(--success)]">
                      Compliance Check Passed
                    </span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="h-4 w-4 text-[var(--destructive)]" />
                    <span className="text-xs font-medium text-[var(--destructive)]">
                      Compliance Check Failed
                    </span>
                  </>
                )}
              </div>

              {complianceCheck && (
                <div className="space-y-1">
                  {complianceCheck.results.map((r) => (
                    <div
                      key={r.rule_id}
                      className="flex items-start gap-2 rounded-md px-2 py-1 text-xs"
                    >
                      {r.passed ? (
                        <CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" />
                      ) : (
                        <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--destructive)]" />
                      )}
                      <div className="min-w-0 flex-1">
                        <span
                          className={
                            r.passed
                              ? "font-medium text-[var(--foreground)]"
                              : "font-medium text-[var(--destructive)]"
                          }
                        >
                          {r.rule_name}
                        </span>
                        <p className="text-[var(--muted-foreground)]">{r.message}</p>
                        {r.current_value && r.limit_value && (
                          <p className="mt-0.5 font-mono text-[10px] text-[var(--muted-foreground)]">
                            Current: {r.current_value} / Limit: {r.limit_value}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
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
        </div>

        {/* Footer: Submit buttons — fixed at bottom */}
        <div className="border-t border-[var(--border)] px-5 py-3">
          {hasComplianceBlock && (
            <p className="mb-2 flex items-center gap-1.5 text-xs text-[var(--destructive)]">
              <ShieldAlert className="h-3.5 w-3.5" />
              Blocked by: {complianceCheck!.blocked_by.join(", ")}
            </p>
          )}
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
                : `${side === "buy" ? "Buy" : "Sell"} ${instrumentId || "..."}${useAlgo ? ` (${algoType.toUpperCase()})` : ""}`}
            </button>
          </div>
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
