"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, ShieldCheck } from "lucide-react";
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

interface TradeTicketInnerProps {
  portfolioId: string;
  onClose: () => void;
  defaults?: { instrument?: string; side?: string; quantity?: string };
  /** When true, show a portfolio dropdown at top */
  showPortfolioSelector?: boolean;
  portfolios?: { id: string; name: string }[];
}

export function TradeTicketInner({ portfolioId: initialPortfolioId, onClose, defaults, showPortfolioSelector, portfolios }: TradeTicketInnerProps) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [portfolioId, setPortfolioId] = useState(initialPortfolioId);

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

  const [complianceCheck, setComplianceCheck] = useState<ComplianceDecision | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);

  const [useAlgo, setUseAlgo] = useState(false);
  const [algoType, setAlgoType] = useState<AlgoType>("twap");
  const [algoDuration, setAlgoDuration] = useState("3600");
  const [algoSlices, setAlgoSlices] = useState("100");
  const [algoVisibleQty, setAlgoVisibleQty] = useState("");

  // Sync defaults when they change (e.g. clicking a different instrument)
  useEffect(() => {
    if (defaults?.instrument) setInstrumentId(defaults.instrument);
    if (defaults?.side) setSide(defaults.side === "sell" ? "sell" : "buy");
    if (defaults?.quantity) setQuantity(defaults.quantity);
  }, [defaults?.instrument, defaults?.side, defaults?.quantity]);

  useEffect(() => {
    setPortfolioId(initialPortfolioId);
  }, [initialPortfolioId]);

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
        // Reset form
        setInstrumentId("");
        setQuantity("");
        setPrice("");
        setRejectionDetail(null);
        setImpact(null);
        setComplianceCheck(null);
        setUseAlgo(false);
      }
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    if (!instrumentId || Number(quantity) <= 0 || Number(price) <= 0) {
      setImpact(null);
      setComplianceCheck(null);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
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
    if (latestPrice) setPrice(latestPrice.mid);
  };

  const hasComplianceBlock =
    complianceCheck && !complianceCheck.approved && complianceCheck.blocked_by.length > 0;

  const canSubmit =
    instrumentId && portfolioId && Number(quantity) > 0 && Number(price) > 0 && !mutation.isPending;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {/* Portfolio selector (panel mode) */}
        {showPortfolioSelector && portfolios && portfolios.length > 1 && (
          <div className="mb-3">
            <span className="mb-1 block text-xs text-[var(--muted-foreground)]">Portfolio</span>
            <select
              value={portfolioId}
              onChange={(e) => setPortfolioId(e.target.value)}
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 text-sm"
            >
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Rejection detail */}
        {rejectionDetail && (
          <div className="mb-3 rounded-md border border-[var(--destructive)]/20 bg-[var(--destructive-muted)] p-3 text-sm text-[var(--destructive)]">
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
            <button type="button" onClick={() => setRejectionDetail(null)} className="mt-2 text-xs underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Side */}
        <div className="mb-3">
          <span className="mb-1 block text-xs text-[var(--muted-foreground)]">Side</span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setSide("buy")}
              className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors ${
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
              className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors ${
                side === "sell"
                  ? "bg-[var(--destructive)] text-white"
                  : "border border-[var(--border)] text-[var(--muted-foreground)]"
              }`}
            >
              Sell
            </button>
          </div>
        </div>

        {/* Instrument search */}
        <div className="relative mb-3">
          <span className="mb-1 block text-xs text-[var(--muted-foreground)]">Instrument</span>
          {instrumentId ? (
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-medium">{instrumentId}</span>
              <button
                type="button"
                onClick={() => { setInstrumentId(""); setShowSearch(true); }}
                className="text-[10px] text-[var(--muted-foreground)] underline"
              >
                change
              </button>
            </div>
          ) : (
            <input
              type="text"
              placeholder="Search instruments..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setShowSearch(true); }}
              onFocus={() => setShowSearch(true)}
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            />
          )}
          {showSearch && searchResults && searchResults.length > 0 && (
            <div className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-[var(--border)] bg-[var(--background)] shadow-lg">
              {searchResults.map((inst) => (
                <button
                  type="button"
                  key={inst.id}
                  onClick={() => selectInstrument(inst.ticker)}
                  className="flex w-full items-center justify-between px-3 py-1.5 text-sm hover:bg-[var(--muted)]"
                >
                  <span className="font-mono font-medium">{inst.ticker}</span>
                  <span className="text-xs text-[var(--muted-foreground)]">{inst.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quantity + Price */}
        <div className="mb-3 grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="panel-qty" className="mb-1 block text-xs text-[var(--muted-foreground)]">Qty</label>
            <input
              id="panel-qty"
              type="number"
              min="0"
              step="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="0"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 font-mono text-sm"
            />
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <label htmlFor="panel-price">Price</label>
              {latestPrice && (
                <button type="button" onClick={handleUseMarketPrice} className="text-[10px] underline">
                  Mid: {latestPrice.mid}
                </button>
              )}
            </div>
            <input
              id="panel-price"
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.00"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 font-mono text-sm"
            />
          </div>
        </div>

        {/* Notional */}
        {Number(quantity) > 0 && Number(price) > 0 && (
          <p className="mb-3 text-xs text-[var(--muted-foreground)]">
            Notional: <span className="font-mono font-medium">${(Number(quantity) * Number(price)).toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
          </p>
        )}

        {/* Execution */}
        <div className="mb-2 border-t border-[var(--border)] pt-2">
          <label className="flex cursor-pointer items-center gap-2 text-xs">
            <input type="checkbox" checked={useAlgo} onChange={(e) => setUseAlgo(e.target.checked)} className="h-3.5 w-3.5 rounded border-[var(--border)]" />
            <span className="text-[var(--muted-foreground)]">Algo execution</span>
          </label>
        </div>

        {useAlgo && (
          <div className="mb-3 space-y-2 rounded-md border border-[var(--border)] bg-[var(--muted)] p-2">
            <div className="flex gap-1">
              {(["twap", "vwap", "iceberg"] as const).map((t) => (
                <button
                  type="button"
                  key={t}
                  onClick={() => setAlgoType(t)}
                  className={`rounded px-2 py-1 text-[10px] font-medium transition-colors ${
                    algoType === t
                      ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                      : "border border-[var(--border)] bg-[var(--background)] text-[var(--muted-foreground)]"
                  }`}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>
            {algoType !== "iceberg" && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label htmlFor="panel-algo-dur" className="mb-0.5 block text-[10px] text-[var(--muted-foreground)]">Duration (s)</label>
                  <input id="panel-algo-dur" type="number" min="60" step="60" value={algoDuration} onChange={(e) => setAlgoDuration(e.target.value)} className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 font-mono text-xs" />
                </div>
                <div>
                  <label htmlFor="panel-algo-slc" className="mb-0.5 block text-[10px] text-[var(--muted-foreground)]">Slices</label>
                  <input id="panel-algo-slc" type="number" min="2" step="1" value={algoSlices} onChange={(e) => setAlgoSlices(e.target.value)} className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 font-mono text-xs" />
                </div>
              </div>
            )}
            {algoType === "iceberg" && (
              <div>
                <label htmlFor="panel-algo-vis" className="mb-0.5 block text-[10px] text-[var(--muted-foreground)]">Visible qty</label>
                <input id="panel-algo-vis" type="number" min="1" step="1" value={algoVisibleQty} onChange={(e) => setAlgoVisibleQty(e.target.value)} placeholder="Auto" className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 font-mono text-xs" />
              </div>
            )}
          </div>
        )}

        {/* Compliance */}
        {(complianceCheck || complianceLoading) && (
          <div className="mb-3 rounded-md border border-[var(--border)] bg-[var(--muted)] p-2">
            <div className="mb-1.5 flex items-center gap-2">
              {complianceLoading ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                  <span className="text-[10px] font-medium text-[var(--muted-foreground)]">Checking compliance...</span>
                </>
              ) : complianceCheck?.approved ? (
                <>
                  <ShieldCheck className="h-3.5 w-3.5 text-[var(--success)]" />
                  <span className="text-[10px] font-medium text-[var(--success)]">Compliance Passed</span>
                </>
              ) : (
                <>
                  <ShieldAlert className="h-3.5 w-3.5 text-[var(--destructive)]" />
                  <span className="text-[10px] font-medium text-[var(--destructive)]">Compliance Failed</span>
                </>
              )}
            </div>
            {complianceCheck && (
              <div className="space-y-1">
                {complianceCheck.results.map((r) => {
                  const badgeColor = r.passed ? "bg-[var(--success)] text-white" : r.severity === "block" ? "bg-[var(--destructive)] text-white" : "bg-[var(--warning)] text-[var(--warning-foreground)]";
                  return (
                    <div key={r.rule_id} className="flex items-center gap-1.5 text-[10px]">
                      <span className={`inline-flex rounded px-1 py-0.5 font-bold uppercase tracking-wide ${badgeColor}`}>
                        {r.passed ? "PASS" : r.severity === "block" ? "BLOCK" : "WARN"}
                      </span>
                      <span className="font-medium text-[var(--foreground)]">{r.rule_name}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Impact */}
        {(impact || impactLoading) && (
          <div className="mb-3 rounded-md border border-[var(--border)] bg-[var(--muted)] p-2">
            <button type="button" onClick={() => setShowImpact(!showImpact)} className="flex w-full items-center justify-between text-xs font-medium">
              Impact Preview
              <span className="text-[10px] text-[var(--muted-foreground)]">{showImpact ? "▾" : "▸"}</span>
            </button>
            {showImpact && (impactLoading ? (
              <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">Calculating...</p>
            ) : impact ? (
              <div className="mt-1 space-y-1">
                <ImpactRow label="NAV" before={fmtUsd(impact.current_nav)} after={fmtUsd(impact.proposed_nav)} delta={impact.nav_change_pct} />
                {impact.current_var_95 && impact.proposed_var_95 && (
                  <ImpactRow label="VaR 95%" before={fmtUsd(impact.current_var_95)} after={fmtUsd(impact.proposed_var_95)} />
                )}
              </div>
            ) : null)}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[var(--border)] px-4 py-3">
        {hasComplianceBlock && (
          <p className="mb-2 flex items-center gap-1.5 text-[10px] text-[var(--destructive)]">
            <ShieldAlert className="h-3 w-3" />
            Blocked by: {complianceCheck!.blocked_by.join(", ")}
          </p>
        )}
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={!canSubmit}
          className={`w-full rounded-md py-2 text-sm font-medium text-white transition-colors ${
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
  );
}

function ImpactRow({ label, before, after, delta }: { label: string; before: string; after: string; delta?: string }) {
  return (
    <div className="flex items-baseline justify-between text-[10px]">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <div className="flex items-baseline gap-1 font-mono">
        <span className="text-[var(--muted-foreground)]">{before}</span>
        <span>→</span>
        <span className="font-medium">{after}</span>
        {delta && (
          <span className={parseFloat(delta) >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}>
            ({parseFloat(delta) >= 0 ? "+" : ""}{parseFloat(delta).toFixed(2)}%)
          </span>
        )}
      </div>
    </div>
  );
}

function fmtUsd(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}
