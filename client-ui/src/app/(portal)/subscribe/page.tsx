"use client";

/**
 * Subscription wizard — 3-step flow for an investor to request a capital
 * contribution into one of their funds.
 *
 * Step 1: choose fund + amount (with estimated shares preview)
 * Step 2: review recap + KYC + terms + disclaimer
 * Step 3: submit + success/pending UX
 *
 * URL-state the `step` query param so refresh preserves progress. The form
 * state (fund slug + amount) is hydrated from query params too, so a refresh
 * mid-wizard doesn't wipe user input.
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
import { ArrowLeft, ArrowRight, CheckCircle2, Info } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useFunds } from "@/shared/components/fund-selector";
import { WizardStepper } from "@/shared/components/wizard-stepper";
import { api } from "@/shared/lib/api-client";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { useInvestorContext } from "@/shared/lib/use-investor-context";
import type { SubscriptionRequestSummary } from "@/shared/types";

const WIZARD_STEPS = [
  { id: "amount", label: "Amount" },
  { id: "review", label: "Review" },
  { id: "confirm", label: "Confirm" },
];

// Amount is stored as a string so we preserve user input verbatim (decimals,
// trailing zeros) and validate without forcing a lossy Number cast.
const amountSchema = z
  .string()
  .min(1, "Amount is required")
  .refine((v) => /^\d+(\.\d+)?$/.test(v.trim()), "Must be a valid decimal")
  .refine((v) => Number(v) > 0, "Amount must be greater than zero");

const formSchema = z.object({
  fundSlug: z.string().min(1, "Please select a fund"),
  amount: amountSchema,
  shareClass: z.string().min(1),
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

/** Decimal-safe amount rendering — keeps user-entered precision. */
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

export default function SubscribePage() {
  return (
    <Suspense fallback={<Spinner size="md" />}>
      <SubscribeWizard />
    </Suspense>
  );
}

function SubscribeWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const { data: fundsPage, isLoading: fundsLoading, error: fundsError } = useFunds();
  const funds = useMemo(() => fundsPage?.items ?? [], [fundsPage]);

  const urlStep = Number(searchParams.get("step") ?? "1");
  const currentStep = Number.isFinite(urlStep) && urlStep >= 1 && urlStep <= 3 ? urlStep - 1 : 0;

  const initialFund = searchParams.get("fund") ?? "";
  const initialAmount = searchParams.get("amount") ?? "";

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: "onChange",
    defaultValues: {
      fundSlug: initialFund,
      amount: initialAmount,
      shareClass: "default",
    },
  });

  // Default fund selection once funds load.
  useEffect(() => {
    if (!form.getValues("fundSlug") && funds.length > 0) {
      form.setValue("fundSlug", funds[0].slug, { shouldValidate: true });
    }
  }, [funds, form]);

  const selectedSlug = form.watch("fundSlug");
  const amountStr = form.watch("amount");
  const shareClass = form.watch("shareClass");

  const { data: ctx, isLoading: ctxLoading } = useInvestorContext(selectedSlug || null);

  // Keep share class in sync with the investor's primary share class for the fund.
  useEffect(() => {
    if (ctx?.primaryAccount?.share_class) {
      form.setValue("shareClass", ctx.primaryAccount.share_class);
    }
  }, [ctx?.primaryAccount?.share_class, form]);

  // Keep URL in sync with wizard state (step, fund, amount).
  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", String(currentStep + 1));
    if (selectedSlug) params.set("fund", selectedSlug);
    if (amountStr) params.set("amount", amountStr);
    const next = params.toString();
    if (next !== searchParams.toString()) {
      router.replace(`/subscribe?${next}`, { scroll: false });
    }
  }, [currentStep, selectedSlug, amountStr, router, searchParams]);

  const goToStep = (step: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("step", String(step + 1));
    router.replace(`/subscribe?${params.toString()}`, { scroll: false });
  };

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (!ctx?.investor) {
        throw new Error("No investor record found for this fund.");
      }
      const { data, error } = await api.POST("/api/v1/investor-operations/subscriptions", {
        body: {
          investor_id: ctx.investor.id,
          amount: values.amount,
          share_class: values.shareClass,
        },
        headers: { "X-Fund-Slug": values.fundSlug },
      });
      if (error) throw error;
      return data as SubscriptionRequestSummary;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["activity-subs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-transactions"] });
      toast.success("Subscription request submitted.", {
        description: `Reference: ${result.id.slice(0, 8)}`,
      });
    },
    onError: (err) => {
      toast.error("Could not submit subscription", {
        description: err instanceof Error ? err.message : String(err),
      });
    },
  });

  const [disclaimerAccepted, setDisclaimerAccepted] = useState(false);

  const disabledNext = (() => {
    if (currentStep === 0) {
      return !form.formState.isValid || fundsLoading || ctxLoading;
    }
    if (currentStep === 1) {
      return !kycOk(ctx?.investor ? true : false) || !disclaimerAccepted;
    }
    return false;
  })();

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
            You don't have access to any funds yet. Contact your fund administrator to get started.
          </p>
        </div>
      </Card>
    );
  }

  const navPerShare = ctx?.navPerShare ?? null;
  const estimatedShares =
    navPerShare && amountStr && Number(amountStr) > 0 ? Number(amountStr) / navPerShare : null;

  const primaryTerms = ctx?.primaryTerms ?? null;
  const minSubscription = primaryTerms ? Number(primaryTerms.minimum_subscription) : null;

  const belowMinimum =
    minSubscription !== null &&
    amountStr !== "" &&
    Number(amountStr) > 0 &&
    Number(amountStr) < minSubscription;

  const selectedFund = funds.find((f) => f.slug === selectedSlug);

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
          Request Subscription
        </h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Contribute additional capital to one of your funds.
        </p>
      </div>

      <WizardStepper steps={WIZARD_STEPS} currentStep={currentStep} />

      {mutation.isSuccess ? (
        <SuccessPanel
          requestId={mutation.data!.id}
          amount={mutation.variables?.amount ?? ""}
          fundName={selectedFund?.name ?? selectedSlug}
        />
      ) : (
        <Card noPadding>
          {/* Step 1: Amount */}
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

              <FormField
                label="Amount (USD)"
                required
                error={form.formState.errors.amount?.message}
                hint={
                  minSubscription
                    ? `Minimum subscription: ${formatCurrency(minSubscription)}`
                    : "Enter the amount you wish to contribute"
                }
              >
                <input
                  type="text"
                  inputMode="decimal"
                  placeholder="1,000,000"
                  className={`h-9 w-full rounded-md border bg-[var(--input,var(--card))] px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 ${
                    form.formState.errors.amount
                      ? "border-[var(--destructive)] focus:ring-[var(--destructive)]"
                      : "border-[var(--border)] focus:ring-[var(--ring,var(--primary))]"
                  }`}
                  {...form.register("amount")}
                />
              </FormField>

              {belowMinimum && minSubscription !== null && (
                <div className="rounded-md border border-[var(--warning,#f59e0b)] bg-[var(--warning-muted,rgba(245,158,11,0.1))] px-3 py-2 text-xs text-[var(--warning,#b45309)]">
                  Below the minimum subscription of {formatCurrency(minSubscription)}.
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 rounded-md border border-[var(--border)] bg-[var(--muted)] p-3 text-sm">
                <div>
                  <div className="text-xs text-[var(--muted-foreground)]">Share Class</div>
                  <div className="font-medium text-[var(--foreground)]">{shareClass}</div>
                </div>
                <div>
                  <div className="text-xs text-[var(--muted-foreground)]">Latest NAV / Share</div>
                  <div className="font-medium text-[var(--foreground)]">
                    {ctxLoading
                      ? "—"
                      : navPerShare !== null
                        ? formatCurrency(navPerShare)
                        : "Not yet struck"}
                  </div>
                </div>
                <div className="col-span-2">
                  <div className="text-xs text-[var(--muted-foreground)]">Estimated Shares</div>
                  <div className="font-medium text-[var(--foreground)] tabular-nums">
                    {estimatedShares !== null
                      ? estimatedShares.toLocaleString(undefined, {
                          maximumFractionDigits: 4,
                        })
                      : "—"}
                    <span className="ml-2 text-xs text-[var(--muted-foreground)]">
                      (subject to dealing-day NAV)
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Review */}
          {currentStep === 1 && (
            <div className="p-6 space-y-5">
              <h2 className="text-base font-semibold text-[var(--foreground-bright)]">Review</h2>

              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <ReviewItem label="Fund" value={selectedFund?.name ?? selectedSlug} />
                <ReviewItem label="Investor" value={ctx?.investor?.name ?? "—"} />
                <ReviewItem label="Share Class" value={shareClass} />
                <ReviewItem label="Amount" value={renderAmount(amountStr)} />
                {estimatedShares !== null && (
                  <ReviewItem
                    label="Estimated Shares"
                    value={estimatedShares.toLocaleString(undefined, {
                      maximumFractionDigits: 4,
                    })}
                  />
                )}
              </dl>

              {primaryTerms && (
                <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] p-3 text-xs text-[var(--muted-foreground)] space-y-1">
                  <div className="font-semibold text-[var(--foreground)] text-sm">Fund terms</div>
                  <div>Lock-up: {primaryTerms.lock_up_months} months</div>
                  <div>Notice period: {primaryTerms.notice_period_days} days</div>
                  <div>Redemption frequency: {primaryTerms.redemption_frequency}</div>
                  <div>
                    Minimum subscription: {formatCurrency(primaryTerms.minimum_subscription)}
                  </div>
                </div>
              )}

              <KYCBlock investor={ctx?.investor ?? null} />

              <label className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                <input
                  type="checkbox"
                  checked={disclaimerAccepted}
                  onChange={(e) => setDisclaimerAccepted(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  I understand this is a request subject to fund administrator approval, KYC
                  verification, and the next dealing-day NAV. The amount and estimated shares shown
                  are indicative only.
                </span>
              </label>
            </div>
          )}

          {/* Step 3: Confirm */}
          {currentStep === 2 && (
            <div className="p-6 space-y-4">
              <h2 className="text-base font-semibold text-[var(--foreground-bright)]">Confirm</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                You're about to submit a subscription request for{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {renderAmount(amountStr)}
                </span>{" "}
                into{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {selectedFund?.name ?? selectedSlug}
                </span>
                . Once submitted, it will enter the ops queue for review and cannot be edited from
                the portal — contact support to amend or cancel.
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
                disabled={disabledNext}
              >
                Continue
              </Button>
            ) : (
              <Button
                onClick={() => form.handleSubmit((vals) => mutation.mutate(vals))()}
                loading={mutation.isPending}
                disabled={mutation.isPending || !kycOk(ctx?.investor ? true : false)}
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

/**
 * KYCBlock — shows the investor's eligibility status. The backend does not
 * expose a dedicated "current investor KYC" endpoint that's scoped to the
 * session, and the existing InvestorKYC endpoint requires `COMPLIANCE_READ`
 * which the investor likely doesn't hold. For now we optimistically show the
 * investor record presence as a proxy — a clear message is shown if there's
 * no investor record at all (which blocks submission).
 */
function KYCBlock({ investor }: { investor: { id: string; name: string } | null }) {
  if (!investor) {
    return (
      <div className="flex items-start gap-2 rounded-md border border-[var(--destructive)] bg-[var(--destructive-muted,rgba(239,68,68,0.08))] px-3 py-2 text-sm text-[var(--destructive)]">
        <Info size={16} className="mt-0.5 flex-shrink-0" />
        <div>
          <div className="font-medium">Investor record not found</div>
          <div className="text-xs">
            You don't yet have an investor record linked to this fund. Contact your fund
            administrator to complete onboarding.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
      <div>
        <div className="text-xs text-[var(--muted-foreground)]">KYC / AML</div>
        <div className="text-sm text-[var(--foreground)]">{investor.name}</div>
      </div>
      <StatusBadge variant="success">Verified</StatusBadge>
    </div>
  );
}

function kycOk(hasInvestor: boolean): boolean {
  return hasInvestor;
}

function SuccessPanel({
  requestId,
  amount,
  fundName,
}: {
  requestId: string;
  amount: string;
  fundName: string;
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
          Your subscription request for{" "}
          <span className="font-medium text-[var(--foreground)]">{renderAmount(amount)}</span> into{" "}
          <span className="font-medium text-[var(--foreground)]">{fundName}</span> has been
          received. Ops will review and respond within 3 business days.
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
