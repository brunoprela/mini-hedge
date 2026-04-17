"use client";

/**
 * Redemption wizard — 3-step flow for an investor to request a capital
 * redemption from one of their funds.
 *
 * Step 1: fund + redemption type (partial/full) + amount (USD) or share count
 * Step 2: review recap + notice period warning + gate check warning
 * Step 3: submit + success/pending UX
 *
 * The submission API accepts a USD amount; share-count input is converted to
 * an amount using the latest NAV per share when the investor chose "shares".
 */

import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorState,
  FormField,
  Select,
  Spinner,
  StatusBadge,
} from "@mini-hedge/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, Info } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useFunds } from "@/shared/components/fund-selector";
import { WizardStepper } from "@/shared/components/wizard-stepper";
import { api } from "@/shared/lib/api-client";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { useInvestorContext } from "@/shared/lib/use-investor-context";
import type { RedemptionRequestSummary } from "@/shared/types";

const WIZARD_STEPS = [
  { id: "amount", label: "Amount" },
  { id: "review", label: "Review" },
  { id: "confirm", label: "Confirm" },
];

const positiveDecimal = z
  .string()
  .min(1, "Required")
  .refine((v) => /^\d+(\.\d+)?$/.test(v.trim()), "Must be a valid decimal")
  .refine((v) => Number(v) > 0, "Must be greater than zero");

const formSchema = z
  .object({
    fundSlug: z.string().min(1, "Please select a fund"),
    redemptionType: z.enum(["partial", "full"]),
    inputMode: z.enum(["amount", "shares"]),
    amount: z.string().optional(),
    shares: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.redemptionType === "partial") {
      if (val.inputMode === "amount") {
        const res = positiveDecimal.safeParse(val.amount ?? "");
        if (!res.success) {
          ctx.addIssue({
            code: "custom",
            path: ["amount"],
            message: res.error.issues[0]?.message ?? "Invalid amount",
          });
        }
      } else {
        const res = positiveDecimal.safeParse(val.shares ?? "");
        if (!res.success) {
          ctx.addIssue({
            code: "custom",
            path: ["shares"],
            message: res.error.issues[0]?.message ?? "Invalid share count",
          });
        }
      }
    }
  });

type FormValues = z.infer<typeof formSchema>;

function formatCurrency(value: number | string) {
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return String(value);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(num);
}

function renderAmount(value: string): string {
  if (!value) return "$0.00";
  const num = Number(value);
  if (!Number.isFinite(num)) return value;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 8,
  }).format(num);
}

export default function RedeemPage() {
  return (
    <Suspense fallback={<Spinner size="md" />}>
      <RedeemWizard />
    </Suspense>
  );
}

function RedeemWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const { data: fundsPage, isLoading: fundsLoading, error: fundsError } = useFunds();
  const funds = useMemo(() => fundsPage?.items ?? [], [fundsPage]);

  const urlStep = Number(searchParams.get("step") ?? "1");
  const currentStep = Number.isFinite(urlStep) && urlStep >= 1 && urlStep <= 3 ? urlStep - 1 : 0;

  const initialFund = searchParams.get("fund") ?? "";
  const initialAmount = searchParams.get("amount") ?? "";
  const initialShares = searchParams.get("shares") ?? "";
  const initialType = (searchParams.get("type") as "partial" | "full" | null) ?? "partial";
  const initialMode = (searchParams.get("mode") as "amount" | "shares" | null) ?? "amount";

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: "onChange",
    defaultValues: {
      fundSlug: initialFund,
      redemptionType: initialType,
      inputMode: initialMode,
      amount: initialAmount,
      shares: initialShares,
    },
  });

  useEffect(() => {
    if (!form.getValues("fundSlug") && funds.length > 0) {
      form.setValue("fundSlug", funds[0].slug, { shouldValidate: true });
    }
  }, [funds, form]);

  const selectedSlug = form.watch("fundSlug");
  const amountStr = form.watch("amount") ?? "";
  const sharesStr = form.watch("shares") ?? "";
  const redemptionType = form.watch("redemptionType");
  const inputMode = form.watch("inputMode");

  const { data: ctx, isLoading: ctxLoading } = useInvestorContext(selectedSlug || null);

  // URL sync.
  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", String(currentStep + 1));
    if (selectedSlug) params.set("fund", selectedSlug);
    params.set("type", redemptionType);
    params.set("mode", inputMode);
    if (amountStr) params.set("amount", amountStr);
    if (sharesStr) params.set("shares", sharesStr);
    const next = params.toString();
    if (next !== searchParams.toString()) {
      router.replace(`/redeem?${next}`, { scroll: false });
    }
  }, [
    currentStep,
    selectedSlug,
    amountStr,
    sharesStr,
    redemptionType,
    inputMode,
    router,
    searchParams,
  ]);

  const goToStep = (step: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", String(step + 1));
    router.replace(`/redeem?${params.toString()}`, { scroll: false });
  };

  const [disclaimerAccepted, setDisclaimerAccepted] = useState(false);

  const primaryAccount = ctx?.primaryAccount ?? null;
  const currentCapital = primaryAccount ? Number(primaryAccount.ending_capital) : null;
  const currentShares = primaryAccount ? Number(primaryAccount.shares_held) : null;
  const navPerShare = ctx?.navPerShare ?? null;
  const primaryTerms = ctx?.primaryTerms ?? null;

  // Resolve the effective USD amount we will submit to the backend.
  const effectiveAmount: number | null = useMemo(() => {
    if (redemptionType === "full") {
      return currentCapital;
    }
    if (inputMode === "amount") {
      const n = Number(amountStr);
      return Number.isFinite(n) && n > 0 ? n : null;
    }
    // shares -> USD via latest NAV per share
    if (navPerShare !== null) {
      const n = Number(sharesStr);
      return Number.isFinite(n) && n > 0 ? n * navPerShare : null;
    }
    return null;
  }, [redemptionType, inputMode, amountStr, sharesStr, currentCapital, navPerShare]);

  const minRedemption = primaryTerms ? Number(primaryTerms.minimum_redemption) : null;
  const belowMinimum =
    minRedemption !== null && effectiveAmount !== null && effectiveAmount < minRedemption;
  const exceedsCapital =
    currentCapital !== null && effectiveAmount !== null && effectiveAmount > currentCapital + 1e-6;

  // Gate check: warn if this single request exceeds the fund's gate % of AUM.
  // We use ending_capital as a lightweight proxy for capital base; a full
  // server-side gate check runs at ops time.
  const gatePct = primaryTerms ? Number(primaryTerms.gate_pct) : null;
  const gateWarning =
    gatePct !== null &&
    currentCapital !== null &&
    effectiveAmount !== null &&
    currentCapital > 0 &&
    effectiveAmount / currentCapital > gatePct;

  const noticeDays = primaryTerms?.notice_period_days ?? null;

  const mutation = useMutation({
    mutationFn: async () => {
      if (!ctx?.investor) {
        throw new Error("No investor record found for this fund.");
      }
      if (effectiveAmount === null || effectiveAmount <= 0) {
        throw new Error("Please enter a valid amount.");
      }
      const { data, error } = await api.POST("/api/v1/investor-operations/redemptions", {
        body: {
          investor_id: ctx.investor.id,
          // Send as a string to preserve decimal precision server-side.
          amount: effectiveAmount.toFixed(2),
          notice_date: null,
        },
        headers: { "X-Fund-Slug": selectedSlug },
      });
      if (error) throw error;
      return data as RedemptionRequestSummary;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["activity-reds"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-transactions"] });
      toast.success("Redemption request submitted.", {
        description: `Reference: ${result.id.slice(0, 8)}`,
      });
    },
    onError: (err) => {
      toast.error("Could not submit redemption", {
        description: err instanceof Error ? err.message : String(err),
      });
    },
  });

  if (fundsError) {
    return <ErrorState message={String(fundsError)} />;
  }

  if (fundsLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
        <Spinner size="sm" /> Loading funds…
      </div>
    );
  }

  if (funds.length === 0) {
    return (
      <Card>
        <div className="p-6 text-center">
          <p className="text-sm font-medium text-[var(--foreground)]">No funds available</p>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            You don't have access to any funds yet. Contact your fund administrator.
          </p>
        </div>
      </Card>
    );
  }

  const selectedFund = funds.find((f) => f.slug === selectedSlug);

  const step1Invalid = (() => {
    if (redemptionType === "full") {
      return !currentCapital || currentCapital <= 0;
    }
    if (inputMode === "amount") {
      return !!form.formState.errors.amount || exceedsCapital || !amountStr;
    }
    if (currentShares !== null && Number(sharesStr) > currentShares + 1e-6) return true;
    return !!form.formState.errors.shares || !sharesStr;
  })();

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <div className="mb-2">
          <Link
            href="/activity"
            className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <ArrowLeft size={12} /> Back to activity
          </Link>
        </div>
        <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">
          Request Redemption
        </h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Withdraw capital from one of your fund holdings.
        </p>
      </div>

      <WizardStepper steps={WIZARD_STEPS} currentStep={currentStep} />

      {mutation.isSuccess ? (
        <SuccessPanel
          requestId={mutation.data!.id}
          amount={String(effectiveAmount ?? "")}
          fundName={selectedFund?.name ?? selectedSlug}
          noticeDays={noticeDays}
        />
      ) : (
        <Card noPadding>
          {/* Step 1 */}
          {currentStep === 0 && (
            <div className="p-6 space-y-4">
              <h2 className="text-base font-semibold text-[var(--foreground-bright)]">Amount</h2>

              {funds.length > 1 && (
                <FormField label="Fund" required>
                  <Select
                    value={selectedSlug}
                    onChange={(e) =>
                      form.setValue("fundSlug", e.target.value, { shouldValidate: true })
                    }
                  >
                    {funds.map((f) => (
                      <option key={f.slug} value={f.slug}>
                        {f.name}
                      </option>
                    ))}
                  </Select>
                </FormField>
              )}

              {funds.length === 1 && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-[var(--foreground)]">Fund</span>
                  <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] px-3 py-2 text-sm text-[var(--foreground)]">
                    {funds[0].name}
                  </div>
                </div>
              )}

              {ctxLoading ? (
                <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
                  <Spinner size="sm" /> Loading account…
                </div>
              ) : !primaryAccount ? (
                <div className="rounded-md border border-[var(--destructive)] bg-[var(--destructive-muted,rgba(239,68,68,0.08))] px-3 py-2 text-sm text-[var(--destructive)]">
                  You have no active capital account in this fund.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3 rounded-md border border-[var(--border)] bg-[var(--muted)] p-3 text-sm">
                  <div>
                    <div className="text-xs text-[var(--muted-foreground)]">Current Capital</div>
                    <div className="font-medium text-[var(--foreground)] tabular-nums">
                      {currentCapital !== null ? formatCurrency(currentCapital) : "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-[var(--muted-foreground)]">Shares Held</div>
                    <div className="font-medium text-[var(--foreground)] tabular-nums">
                      {currentShares !== null
                        ? currentShares.toLocaleString(undefined, {
                            maximumFractionDigits: 4,
                          })
                        : "—"}
                    </div>
                  </div>
                </div>
              )}

              <FormField label="Type" required>
                <div className="flex gap-2" role="radiogroup">
                  {(["partial", "full"] as const).map((t) => {
                    const active = redemptionType === t;
                    return (
                      <button
                        key={t}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => form.setValue("redemptionType", t, { shouldValidate: true })}
                        className={`flex-1 rounded-md border px-3 py-2 text-sm transition-colors ${
                          active
                            ? "border-[var(--primary)] bg-[var(--primary-muted,rgba(59,130,246,0.1))] text-[var(--foreground)]"
                            : "border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                        }`}
                      >
                        <div className="font-medium capitalize">{t}</div>
                        <div className="text-xs text-[var(--muted-foreground)]">
                          {t === "partial"
                            ? "Redeem a specific amount or share count"
                            : "Redeem all capital in this fund"}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </FormField>

              {redemptionType === "partial" && (
                <>
                  <FormField label="Input as" required>
                    <div className="flex gap-2" role="radiogroup">
                      {(["amount", "shares"] as const).map((m) => {
                        const active = inputMode === m;
                        return (
                          <button
                            key={m}
                            type="button"
                            role="radio"
                            aria-checked={active}
                            onClick={() => form.setValue("inputMode", m, { shouldValidate: true })}
                            className={`rounded-md border px-3 py-1.5 text-xs capitalize ${
                              active
                                ? "border-[var(--primary)] bg-[var(--primary-muted,rgba(59,130,246,0.1))] text-[var(--foreground)]"
                                : "border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                            }`}
                          >
                            {m === "amount" ? "USD amount" : "Share count"}
                          </button>
                        );
                      })}
                    </div>
                  </FormField>

                  {inputMode === "amount" ? (
                    <FormField
                      label="Amount (USD)"
                      required
                      error={
                        form.formState.errors.amount?.message ??
                        (exceedsCapital ? "Exceeds your current capital in this fund." : undefined)
                      }
                      hint={
                        minRedemption !== null
                          ? `Minimum redemption: ${formatCurrency(minRedemption)}`
                          : "Amount you wish to redeem"
                      }
                    >
                      <input
                        type="text"
                        inputMode="decimal"
                        placeholder="500000"
                        className={`h-9 w-full rounded-md border bg-[var(--input,var(--card))] px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 ${
                          form.formState.errors.amount || exceedsCapital
                            ? "border-[var(--destructive)] focus:ring-[var(--destructive)]"
                            : "border-[var(--border)] focus:ring-[var(--ring,var(--primary))]"
                        }`}
                        {...form.register("amount")}
                      />
                    </FormField>
                  ) : (
                    <FormField
                      label="Shares"
                      required
                      error={
                        form.formState.errors.shares?.message ??
                        (currentShares !== null && Number(sharesStr) > currentShares + 1e-6
                          ? "Exceeds shares held."
                          : undefined)
                      }
                      hint={
                        navPerShare !== null
                          ? `Approx ${formatCurrency((Number(sharesStr) || 0) * navPerShare)} at latest NAV`
                          : "Latest NAV not yet available"
                      }
                    >
                      <input
                        type="text"
                        inputMode="decimal"
                        placeholder="1000"
                        className={`h-9 w-full rounded-md border bg-[var(--input,var(--card))] px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 ${
                          form.formState.errors.shares
                            ? "border-[var(--destructive)] focus:ring-[var(--destructive)]"
                            : "border-[var(--border)] focus:ring-[var(--ring,var(--primary))]"
                        }`}
                        {...form.register("shares")}
                      />
                    </FormField>
                  )}

                  {belowMinimum && minRedemption !== null && (
                    <div className="rounded-md border border-[var(--warning,#f59e0b)] bg-[var(--warning-muted,rgba(245,158,11,0.1))] px-3 py-2 text-xs text-[var(--warning,#b45309)]">
                      Below the minimum redemption of {formatCurrency(minRedemption)}.
                    </div>
                  )}
                </>
              )}

              {redemptionType === "full" && currentCapital !== null && (
                <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] p-3 text-sm">
                  <div className="text-xs text-[var(--muted-foreground)]">
                    Full redemption amount
                  </div>
                  <div className="font-medium text-[var(--foreground)] tabular-nums">
                    {formatCurrency(currentCapital)}
                  </div>
                </div>
              )}

              {/* Fee/gate preview */}
              {(noticeDays || gatePct !== null) && (
                <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3 text-xs text-[var(--muted-foreground)] space-y-0.5">
                  {noticeDays !== null && <div>Notice period: {noticeDays} days</div>}
                  {gatePct !== null && (
                    <div>
                      Gate: {(gatePct * 100).toFixed(1)}% of capital base per dealing day (prorated
                      if exceeded)
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 2 */}
          {currentStep === 1 && (
            <div className="p-6 space-y-5">
              <h2 className="text-base font-semibold text-[var(--foreground-bright)]">Review</h2>

              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <ReviewItem label="Fund" value={selectedFund?.name ?? selectedSlug} />
                <ReviewItem label="Investor" value={ctx?.investor?.name ?? "—"} />
                <ReviewItem
                  label="Type"
                  value={redemptionType === "full" ? "Full redemption" : "Partial redemption"}
                />
                <ReviewItem
                  label="Amount"
                  value={effectiveAmount !== null ? formatCurrency(effectiveAmount) : "—"}
                />
                {redemptionType === "partial" && inputMode === "shares" && (
                  <ReviewItem label="Shares" value={sharesStr || "—"} />
                )}
              </dl>

              {noticeDays !== null && noticeDays > 0 && (
                <div className="flex items-start gap-2 rounded-md border border-[var(--warning,#f59e0b)] bg-[var(--warning-muted,rgba(245,158,11,0.1))] px-3 py-2 text-sm text-[var(--warning,#b45309)]">
                  <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">Notice period: {noticeDays} days</div>
                    <div className="text-xs">
                      Requests received after the notice cut-off will be deferred to the following
                      dealing date.
                    </div>
                  </div>
                </div>
              )}

              {gateWarning && gatePct !== null && (
                <div className="flex items-start gap-2 rounded-md border border-[var(--warning,#f59e0b)] bg-[var(--warning-muted,rgba(245,158,11,0.1))] px-3 py-2 text-sm text-[var(--warning,#b45309)]">
                  <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">Possible gate</div>
                    <div className="text-xs">
                      This request is larger than the fund's {(gatePct * 100).toFixed(1)}% gate
                      relative to your capital base. It may be pro-rated by the fund administrator
                      at dealing-day execution.
                    </div>
                  </div>
                </div>
              )}

              <InvestorBlock investor={ctx?.investor ?? null} />

              <label className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                <input
                  type="checkbox"
                  checked={disclaimerAccepted}
                  onChange={(e) => setDisclaimerAccepted(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  I understand this redemption is subject to the fund's notice period, gate, and
                  next dealing-day NAV. The amount shown is indicative only and may be pro-rated.
                </span>
              </label>
            </div>
          )}

          {/* Step 3 */}
          {currentStep === 2 && (
            <div className="p-6 space-y-4">
              <h2 className="text-base font-semibold text-[var(--foreground-bright)]">Confirm</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                You're about to submit a redemption request for{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {effectiveAmount !== null ? formatCurrency(effectiveAmount) : "—"}
                </span>{" "}
                from{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {selectedFund?.name ?? selectedSlug}
                </span>
                . Once submitted, it will enter the ops queue for validation.
              </p>
              {mutation.isError && (
                <div className="rounded-md border border-[var(--destructive)] bg-[var(--destructive-muted,rgba(239,68,68,0.1))] px-3 py-2 text-sm text-[var(--destructive)]">
                  {mutation.error instanceof Error
                    ? mutation.error.message
                    : String(mutation.error)}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between border-t border-[var(--border)] px-4 py-3">
            <Button
              variant="ghost"
              onClick={() =>
                currentStep === 0 ? router.push("/activity") : goToStep(currentStep - 1)
              }
              leadingIcon={<ArrowLeft size={14} />}
              disabled={mutation.isPending}
            >
              {currentStep === 0 ? "Cancel" : "Back"}
            </Button>
            {currentStep < 2 ? (
              <Button
                onClick={() => goToStep(currentStep + 1)}
                trailingIcon={<ArrowRight size={14} />}
                disabled={
                  ctxLoading ||
                  !ctx?.investor ||
                  !primaryAccount ||
                  (currentStep === 0 && step1Invalid) ||
                  (currentStep === 1 && !disclaimerAccepted)
                }
              >
                Continue
              </Button>
            ) : (
              <Button
                onClick={() => mutation.mutate()}
                loading={mutation.isPending}
                disabled={
                  mutation.isPending ||
                  !ctx?.investor ||
                  effectiveAmount === null ||
                  effectiveAmount <= 0
                }
              >
                Submit Request
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-[var(--muted-foreground)]">{label}</dt>
      <dd className="mt-0.5 font-medium text-[var(--foreground)] tabular-nums">{value}</dd>
    </div>
  );
}

function InvestorBlock({ investor }: { investor: { id: string; name: string } | null }) {
  if (!investor) {
    return (
      <div className="flex items-start gap-2 rounded-md border border-[var(--destructive)] bg-[var(--destructive-muted,rgba(239,68,68,0.08))] px-3 py-2 text-sm text-[var(--destructive)]">
        <Info size={16} className="mt-0.5 flex-shrink-0" />
        <div>
          <div className="font-medium">Investor record not found</div>
          <div className="text-xs">You don't yet have an investor record linked to this fund.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
      <div>
        <div className="text-xs text-[var(--muted-foreground)]">Investor</div>
        <div className="text-sm text-[var(--foreground)]">{investor.name}</div>
      </div>
      <StatusBadge variant="success">Verified</StatusBadge>
    </div>
  );
}

function SuccessPanel({
  requestId,
  amount,
  fundName,
  noticeDays,
}: {
  requestId: string;
  amount: string;
  fundName: string;
  noticeDays: number | null;
}) {
  const router = useRouter();
  return (
    <Card noPadding>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CheckCircle2 size={18} className="text-[var(--success)]" />
          <h2 className="text-base font-semibold text-[var(--foreground-bright)]">
            Request submitted
          </h2>
        </div>
      </CardHeader>
      <CardBody>
        <p className="text-sm text-[var(--muted-foreground)]">
          Your redemption request for{" "}
          <span className="font-medium text-[var(--foreground)]">{renderAmount(amount)}</span> from{" "}
          <span className="font-medium text-[var(--foreground)]">{fundName}</span> has been
          received.{" "}
          {noticeDays
            ? `It will be processed at the next dealing date after the ${noticeDays}-day notice period.`
            : "Ops will review and respond within 3 business days."}
        </p>
        <div className="mt-4 rounded-md border border-[var(--border)] bg-[var(--muted)] px-3 py-2 text-xs">
          <span className="text-[var(--muted-foreground)]">Reference:</span>{" "}
          <span className="font-mono text-[var(--foreground)]">{requestId}</span>
        </div>
        <div className="mt-5 flex gap-2">
          <Button onClick={() => router.push("/activity")}>View activity</Button>
          <Button variant="secondary" onClick={() => router.push("/")}>
            Back to dashboard
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
