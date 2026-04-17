"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, ChevronRight, ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Controller } from "react-hook-form";
import { toast } from "sonner";
import { runWhatIf } from "@/features/alpha/api";
import type { WhatIfResult } from "@/features/alpha/types";
import { type ComplianceDecision, checkTradeCompliance } from "@/features/compliance/api";
import { instrumentSearchQueryOptions } from "@/features/instruments/api";
import { latestPriceQueryOptions } from "@/features/market-data/api";
import { createAlgoOrder, createOrder } from "@/features/orders/api";
import type { AlgoType, OrderSummary } from "@/features/orders/types";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { type TradeTicketFormState, useTradeTicketStore } from "@/shared/stores/trade-ticket-store";

interface TradeTicketInnerProps {
  portfolioId: string;
  onClose: () => void;
  defaults?: { instrument?: string; side?: string; quantity?: string };
  /** When true, show a portfolio dropdown at top */
  showPortfolioSelector?: boolean;
  portfolios?: { id: string; name: string }[];
}

/* ------------------------------------------------------------------ */
/*  Schema                                                             */
/* ------------------------------------------------------------------ */

/**
 * String field that must parse to a positive number.  We keep these as
 * strings so the `<input type="number">` stays controlled via RHF's
 * `register(...)` without reaching into value coercion on every keystroke.
 * Compliance/impact previews and submit gating re-parse as needed.
 */
const positiveNumberString = z
  .string()
  .refine((v) => v === "" || (!Number.isNaN(parseFloat(v)) && parseFloat(v) > 0), {
    message: "Must be a positive number",
  });

const tradeTicketSchema = z
  .object({
    instrument: z.string(),
    side: z.enum(["buy", "sell"]),
    quantity: positiveNumberString,
    price: positiveNumberString,
    useAlgo: z.boolean(),
    algoType: z.enum(["twap", "vwap", "iceberg"]),
    algoDuration: z.string(),
    algoSlices: z.string(),
    algoVisibleQty: z.string(),
  })
  .superRefine((val, ctx) => {
    if (val.useAlgo) {
      if (val.algoType !== "iceberg") {
        const dur = parseInt(val.algoDuration, 10);
        if (Number.isNaN(dur) || dur < 60) {
          ctx.addIssue({
            code: "custom",
            path: ["algoDuration"],
            message: "Duration must be ≥ 60 seconds",
          });
        }
        const slices = parseInt(val.algoSlices, 10);
        if (Number.isNaN(slices) || slices < 2) {
          ctx.addIssue({
            code: "custom",
            path: ["algoSlices"],
            message: "Must have at least 2 slices",
          });
        }
      }
    }
  });

type TradeTicketFormValues = z.infer<typeof tradeTicketSchema>;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function TradeTicketInner({
  portfolioId: initialPortfolioId,
  onClose: _onClose,
  defaults,
  showPortfolioSelector,
  portfolios,
}: TradeTicketInnerProps) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  /* ---- Zustand-backed persisted form state ---- */
  // Hydrate default values synchronously from the persisted store so a
  // refresh keeps the ticket open with filled values.
  const initialFormState = useRef<TradeTicketFormState>(useTradeTicketStore.getState().formState);
  const resetStoreForm = useTradeTicketStore((s) => s.resetForm);

  const form = useForm<TradeTicketFormValues>({
    resolver: zodResolver(tradeTicketSchema),
    defaultValues: initialFormState.current,
    mode: "onChange",
  });

  // Keep Zustand in sync with RHF so the existing sessionStorage
  // persistence keeps working transparently.
  useEffect(() => {
    const sub = form.watch((values) => {
      useTradeTicketStore.setState({
        formState: values as TradeTicketFormState,
      });
    });
    return () => sub.unsubscribe();
  }, [form]);

  // Watch live for UI reactivity (buttons, notional, submit label, etc.)
  const side = form.watch("side");
  const instrumentId = form.watch("instrument");
  const quantity = form.watch("quantity");
  const price = form.watch("price");
  const useAlgo = form.watch("useAlgo");
  const algoType = form.watch("algoType");

  /* ---- Local-only ephemeral state ---- */
  const [portfolioId, setPortfolioId] = useState(initialPortfolioId);
  const [search, setSearch] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [rejectionDetail, setRejectionDetail] = useState<OrderSummary | null>(null);
  const [impact, setImpact] = useState<WhatIfResult | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [complianceOpen, setComplianceOpen] = useState(true);
  const [impactOpen, setImpactOpen] = useState(false);
  const [complianceCheck, setComplianceCheck] = useState<ComplianceDecision | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [confirmedOrder, setConfirmedOrder] = useState<{
    id: string;
    instrument_id: string;
    side: string;
    quantity: string;
  } | null>(null);

  // Sync defaults when they change (e.g. clicking a different instrument).
  // Callers still go through the Zustand-driven "open trade ticket with
  // prefilled values" flow and we mirror those defaults onto the form via
  // setValue so RHF's internal state stays authoritative.
  const setValue = form.setValue;
  useEffect(() => {
    if (defaults?.instrument) {
      setValue("instrument", defaults.instrument, { shouldValidate: true });
    }
    if (defaults?.side) {
      setValue("side", defaults.side === "sell" ? "sell" : "buy");
    }
    if (defaults?.quantity) {
      setValue("quantity", defaults.quantity, { shouldValidate: true });
    }
  }, [defaults?.instrument, defaults?.side, defaults?.quantity, setValue]);

  useEffect(() => {
    setPortfolioId(initialPortfolioId);
  }, [initialPortfolioId]);

  // Auto-clear confirmation strip when user starts entering a new order
  useEffect(() => {
    if (instrumentId || quantity || price) {
      setConfirmedOrder(null);
    }
  }, [instrumentId, quantity, price]);

  const handleNewOrder = () => {
    setConfirmedOrder(null);
    resetStoreForm();
    form.reset(useTradeTicketStore.getState().formState);
    setRejectionDetail(null);
    setImpact(null);
    setComplianceCheck(null);
  };

  const { data: searchResults } = useQuery(instrumentSearchQueryOptions(fundSlug, search));

  const { data: latestPrice } = useQuery({
    ...latestPriceQueryOptions(fundSlug, instrumentId),
    enabled: instrumentId.length > 0,
  });

  // Optimistic trade submission: immediately insert a provisional order into
  // the orders cache (marked as "pending"), then reconcile with the server
  // response in onSuccess, or roll back in onError.
  const mutation = useMutation({
    mutationFn: (values: TradeTicketFormValues) => {
      if (values.useAlgo) {
        return createAlgoOrder(fundSlug, {
          portfolio_id: portfolioId,
          instrument_id: values.instrument,
          side: values.side,
          order_type: "limit",
          quantity: values.quantity,
          limit_price: values.price,
          time_in_force: "day",
          algo_type: values.algoType,
          algo_params: {
            duration_seconds: parseInt(values.algoDuration, 10) || 3600,
            num_slices: parseInt(values.algoSlices, 10) || 100,
            ...(values.algoType === "iceberg" && values.algoVisibleQty
              ? { visible_quantity: values.algoVisibleQty }
              : {}),
          },
        });
      }
      return createOrder(fundSlug, {
        portfolio_id: portfolioId,
        instrument_id: values.instrument,
        side: values.side,
        order_type: "market",
        quantity: values.quantity,
        limit_price: values.price,
        time_in_force: "day",
      });
    },
    onMutate: async (values) => {
      const queryKey = ["orders", fundSlug, portfolioId];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<OrderSummary[]>(queryKey);
      const tempId = `temp-${Date.now()}`;
      const optimisticOrder = {
        id: tempId,
        portfolio_id: portfolioId,
        instrument_id: values.instrument,
        side: values.side,
        order_type: values.useAlgo ? "limit" : "market",
        quantity: values.quantity,
        limit_price: values.price,
        filled_quantity: "0",
        avg_fill_price: null,
        time_in_force: "day",
        broker_id: null,
        state: "pending",
        created_at: new Date().toISOString(),
        ...(values.useAlgo
          ? { algo_type: values.algoType, is_parent: true, children_count: 0, children_filled: 0 }
          : {}),
      } as unknown as OrderSummary;
      queryClient.setQueryData<OrderSummary[] | undefined>(queryKey, (old) => [
        optimisticOrder,
        ...(old ?? []),
      ]);
      return { previous, queryKey, tempId };
    },
    onSuccess: (order, values) => {
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio-summary"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["exposure"] });

      if (order.state === "rejected") {
        setRejectionDetail(order);
        toast.error("Order rejected by compliance");
      } else {
        setConfirmedOrder({
          id: order.id,
          instrument_id: order.instrument_id,
          side: order.side,
          quantity: order.quantity,
        });
        toast.success(
          `${values.side.toUpperCase()} ${values.quantity} ${values.instrument} — ${order.state}`,
        );
        // Reset form (both RHF and Zustand)
        resetStoreForm();
        form.reset(useTradeTicketStore.getState().formState);
        setRejectionDetail(null);
        setImpact(null);
        setComplianceCheck(null);
      }
    },
    onError: (err: Error, _vars, context) => {
      if (context?.previous && context.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
      toast.error(err.message);
    },
  });

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

  // Live impact/compliance preview — debounced off field changes that
  // materially affect the order shape.  Uses the values watched above so
  // RHF's internal state is the single source of truth.
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
    form.setValue("instrument", ticker, { shouldValidate: true, shouldDirty: true });
    setSearch("");
    setShowSearch(false);
  }

  const handleUseMarketPrice = () => {
    if (latestPrice)
      form.setValue("price", latestPrice.mid, { shouldValidate: true, shouldDirty: true });
  };

  const hasComplianceBlock =
    complianceCheck && !complianceCheck.approved && complianceCheck.blocked_by.length > 0;

  const canSubmit =
    instrumentId && portfolioId && Number(quantity) > 0 && Number(price) > 0 && !mutation.isPending;

  const onSubmit = form.handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <form onSubmit={onSubmit} className="flex h-full flex-col">
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
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Order confirmation strip */}
        {confirmedOrder && (
          <div className="mb-3 rounded-md border border-[var(--success)]/30 bg-[var(--success)]/10 p-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--success)]" />
              <span className="text-sm font-medium text-[var(--success)]">Order Submitted</span>
            </div>
            <p className="mt-1.5 pl-6 font-mono text-xs text-[var(--foreground)]">
              {confirmedOrder.side.toUpperCase()} {confirmedOrder.quantity}{" "}
              {confirmedOrder.instrument_id}
            </p>
            <p className="mt-0.5 pl-6 text-[10px] text-[var(--muted-foreground)]">
              ID: {confirmedOrder.id.slice(0, 8)}
            </p>
            <div className="mt-2 flex items-center gap-2 pl-6">
              <Link
                href={`/${fundSlug}/orders`}
                className="rounded-md bg-[var(--success)]/15 px-2 py-1 text-[10px] font-medium text-[var(--success)] transition-colors hover:bg-[var(--success)]/25"
              >
                View Orders
              </Link>
              <button
                type="button"
                onClick={handleNewOrder}
                className="rounded-md border border-[var(--border)] px-2 py-1 text-[10px] font-medium text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)]"
              >
                New Order
              </button>
            </div>
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
            <button
              type="button"
              onClick={() => setRejectionDetail(null)}
              className="mt-2 text-xs underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Side */}
        <div className="mb-3">
          <span className="mb-1 block text-xs text-[var(--muted-foreground)]">Side</span>
          <Controller
            control={form.control}
            name="side"
            render={({ field }) => (
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => field.onChange("buy")}
                  className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors ${
                    field.value === "buy"
                      ? "bg-[var(--success)] text-white"
                      : "border border-[var(--border)] text-[var(--muted-foreground)]"
                  }`}
                >
                  Buy
                </button>
                <button
                  type="button"
                  onClick={() => field.onChange("sell")}
                  className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors ${
                    field.value === "sell"
                      ? "bg-[var(--destructive)] text-white"
                      : "border border-[var(--border)] text-[var(--muted-foreground)]"
                  }`}
                >
                  Sell
                </button>
              </div>
            )}
          />
        </div>

        {/* Instrument search */}
        <div className="relative mb-3">
          <span className="mb-1 block text-xs text-[var(--muted-foreground)]">Instrument</span>
          {instrumentId ? (
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-medium">{instrumentId}</span>
              <button
                type="button"
                onClick={() => {
                  form.setValue("instrument", "", { shouldValidate: true });
                  setShowSearch(true);
                }}
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
              onChange={(e) => {
                setSearch(e.target.value);
                setShowSearch(true);
              }}
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
            <label
              htmlFor="panel-qty"
              className="mb-1 block text-xs text-[var(--muted-foreground)]"
            >
              Qty
            </label>
            <input
              id="panel-qty"
              type="number"
              min="0"
              step="1"
              placeholder="0"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 font-mono text-sm"
              aria-invalid={form.formState.errors.quantity ? true : undefined}
              {...form.register("quantity")}
            />
            {form.formState.errors.quantity?.message && (
              <p className="mt-1 text-[10px] text-[var(--destructive)]">
                {form.formState.errors.quantity.message}
              </p>
            )}
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <label htmlFor="panel-price">Price</label>
              {latestPrice && (
                <button
                  type="button"
                  onClick={handleUseMarketPrice}
                  className="text-[10px] underline"
                >
                  Mid: {latestPrice.mid}
                </button>
              )}
            </div>
            <input
              id="panel-price"
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 font-mono text-sm"
              aria-invalid={form.formState.errors.price ? true : undefined}
              {...form.register("price")}
            />
            {form.formState.errors.price?.message && (
              <p className="mt-1 text-[10px] text-[var(--destructive)]">
                {form.formState.errors.price.message}
              </p>
            )}
          </div>
        </div>

        {/* Notional */}
        {Number(quantity) > 0 && Number(price) > 0 && (
          <p className="mb-3 text-xs text-[var(--muted-foreground)]">
            Notional:{" "}
            <span className="font-mono font-medium">
              $
              {(Number(quantity) * Number(price)).toLocaleString("en-US", {
                minimumFractionDigits: 2,
              })}
            </span>
          </p>
        )}

        {/* Execution */}
        <div className="mb-2 border-t border-[var(--border)] pt-2">
          <label className="flex cursor-pointer items-center gap-2 text-xs">
            <input
              type="checkbox"
              className="h-3.5 w-3.5 rounded border-[var(--border)]"
              {...form.register("useAlgo")}
            />
            <span className="text-[var(--muted-foreground)]">Algo execution</span>
          </label>
        </div>

        {useAlgo && (
          <div className="mb-3 space-y-2 rounded-md border border-[var(--border)] bg-[var(--muted)] p-2">
            <Controller
              control={form.control}
              name="algoType"
              render={({ field }) => (
                <div className="flex gap-1">
                  {(["twap", "vwap", "iceberg"] as const).map((t) => (
                    <button
                      type="button"
                      key={t}
                      onClick={() => field.onChange(t as AlgoType)}
                      className={`rounded px-2 py-1 text-[10px] font-medium transition-colors ${
                        field.value === t
                          ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                          : "border border-[var(--border)] bg-[var(--background)] text-[var(--muted-foreground)]"
                      }`}
                    >
                      {t.toUpperCase()}
                    </button>
                  ))}
                </div>
              )}
            />
            {algoType !== "iceberg" && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label
                    htmlFor="panel-algo-dur"
                    className="mb-0.5 block text-[10px] text-[var(--muted-foreground)]"
                  >
                    Duration (s)
                  </label>
                  <input
                    id="panel-algo-dur"
                    type="number"
                    min="60"
                    step="60"
                    className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 font-mono text-xs"
                    aria-invalid={form.formState.errors.algoDuration ? true : undefined}
                    {...form.register("algoDuration")}
                  />
                  {form.formState.errors.algoDuration?.message && (
                    <p className="mt-0.5 text-[10px] text-[var(--destructive)]">
                      {form.formState.errors.algoDuration.message}
                    </p>
                  )}
                </div>
                <div>
                  <label
                    htmlFor="panel-algo-slc"
                    className="mb-0.5 block text-[10px] text-[var(--muted-foreground)]"
                  >
                    Slices
                  </label>
                  <input
                    id="panel-algo-slc"
                    type="number"
                    min="2"
                    step="1"
                    className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 font-mono text-xs"
                    aria-invalid={form.formState.errors.algoSlices ? true : undefined}
                    {...form.register("algoSlices")}
                  />
                  {form.formState.errors.algoSlices?.message && (
                    <p className="mt-0.5 text-[10px] text-[var(--destructive)]">
                      {form.formState.errors.algoSlices.message}
                    </p>
                  )}
                </div>
              </div>
            )}
            {algoType === "iceberg" && (
              <div>
                <label
                  htmlFor="panel-algo-vis"
                  className="mb-0.5 block text-[10px] text-[var(--muted-foreground)]"
                >
                  Visible qty
                </label>
                <input
                  id="panel-algo-vis"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="Auto"
                  className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 font-mono text-xs"
                  {...form.register("algoVisibleQty")}
                />
              </div>
            )}
          </div>
        )}

        {/* Compliance */}
        {(complianceCheck || complianceLoading) && (
          <CollapsibleSection
            title={
              <div className="flex items-center gap-2">
                {complianceLoading ? (
                  <>
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                    <span className="text-[10px] font-medium text-[var(--muted-foreground)]">
                      Checking compliance...
                    </span>
                  </>
                ) : complianceCheck?.approved ? (
                  <>
                    <ShieldCheck className="h-3.5 w-3.5 text-[var(--success)]" />
                    <span className="text-[10px] font-medium text-[var(--success)]">
                      Compliance Passed
                    </span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="h-3.5 w-3.5 text-[var(--destructive)]" />
                    <span className="text-[10px] font-medium text-[var(--destructive)]">
                      Compliance Failed
                    </span>
                  </>
                )}
              </div>
            }
            open={complianceOpen}
            onToggle={() => setComplianceOpen((v) => !v)}
          >
            {complianceCheck && (
              <div className="space-y-1">
                {complianceCheck.results.map((r) => {
                  const badgeColor = r.passed
                    ? "bg-[var(--success)] text-white"
                    : r.severity === "block"
                      ? "bg-[var(--destructive)] text-white"
                      : "bg-[var(--warning)] text-[var(--warning-foreground)]";
                  return (
                    <div key={r.rule_id} className="flex items-center gap-1.5 text-[10px]">
                      <span
                        className={`inline-flex rounded px-1 py-0.5 font-bold uppercase tracking-wide ${badgeColor}`}
                      >
                        {r.passed ? "PASS" : r.severity === "block" ? "BLOCK" : "WARN"}
                      </span>
                      <span className="font-medium text-[var(--foreground)]">{r.rule_name}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </CollapsibleSection>
        )}

        {/* Impact */}
        {(impact || impactLoading) && (
          <CollapsibleSection
            title="Impact Preview"
            open={impactOpen}
            onToggle={() => setImpactOpen((v) => !v)}
          >
            {impactLoading ? (
              <p className="text-[10px] text-[var(--muted-foreground)]">Calculating...</p>
            ) : impact ? (
              <div className="space-y-1">
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
              </div>
            ) : null}
          </CollapsibleSection>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[var(--border)] px-4 py-3">
        {hasComplianceBlock && (
          <p className="mb-2 flex items-center gap-1.5 text-[10px] text-[var(--destructive)]">
            <ShieldAlert className="h-3 w-3" />
            Blocked by: {complianceCheck?.blocked_by.join(", ")}
          </p>
        )}
        <button
          type="submit"
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
    </form>
  );
}

function CollapsibleSection({
  title,
  open,
  onToggle,
  children,
}: {
  title: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <div className="mb-3 rounded-md border border-[var(--border)] bg-[var(--muted)]">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-2 py-1.5"
      >
        {typeof title === "string" ? (
          <span className="text-xs font-medium text-[var(--foreground)]">{title}</span>
        ) : (
          title
        )}
        <Chevron className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)] transition-transform duration-150" />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-150 ease-out"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="px-2 pb-2">{children}</div>
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
    <div className="flex items-baseline justify-between text-[10px]">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <div className="flex items-baseline gap-1 font-mono">
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
