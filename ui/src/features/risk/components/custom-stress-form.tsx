"use client";

import { FormField } from "@mini-hedge/ui";
import { useMutation } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { useFieldArray } from "react-hook-form";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { runCustomStressTest } from "../api";
import type { StressTestResult } from "../types";

function fmtCurrency(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmtPct(v: string) {
  return `${parseFloat(v).toFixed(2)}%`;
}

/* ------------------------------------------------------------------ */
/*  Schema                                                             */
/* ------------------------------------------------------------------ */

const shockSchema = z.object({
  factor: z.string().trim().min(1, "Factor is required"),
  value: z
    .string()
    .trim()
    .min(1, "Shock value is required")
    .refine((v) => !Number.isNaN(parseFloat(v)), "Must be a number"),
});

const customStressSchema = z.object({
  name: z.string().trim().min(1, "Scenario name is required"),
  description: z.string().trim().optional(),
  shocks: z.array(shockSchema).min(1, "Add at least one shock"),
});

type CustomStressValues = z.infer<typeof customStressSchema>;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CustomStressForm({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const [result, setResult] = useState<StressTestResult | null>(null);

  const form = useForm<CustomStressValues>({
    resolver: zodResolver(customStressSchema),
    defaultValues: {
      name: "",
      description: "",
      shocks: [{ factor: "", value: "" }],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "shocks",
  });

  const mutation = useMutation({
    mutationFn: (data: { name: string; shocks: Record<string, number>; description?: string }) =>
      runCustomStressTest(fundSlug, portfolioId, data),
    onSuccess: (data) => {
      setResult(data);
      toast.success("Custom stress test completed");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to run stress test");
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    const shocksDict: Record<string, number> = {};
    for (const s of values.shocks) {
      shocksDict[s.factor.trim()] = parseFloat(s.value);
    }
    mutation.mutate({
      name: values.name.trim(),
      shocks: shocksDict,
      description: values.description?.trim() || undefined,
    });
  });

  const pnl = result ? parseFloat(result.total_pnl_impact) : 0;
  const shockErrors = form.formState.errors.shocks;

  return (
    <div className="space-y-2">
      <form
        onSubmit={onSubmit}
        className="space-y-2 rounded-md border border-[var(--border)] bg-[var(--card)] p-3"
      >
        <div className="grid gap-2 sm:grid-cols-2">
          <FormField
            label="Scenario Name"
            required
            error={form.formState.errors.name?.message}
          >
            <input
              id="stress-scenario-name"
              type="text"
              placeholder="e.g. Equity crash"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)]"
              {...form.register("name")}
            />
          </FormField>
          <FormField
            label="Description"
            error={form.formState.errors.description?.message}
          >
            <input
              id="stress-description"
              type="text"
              placeholder="Optional"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)]"
              {...form.register("description")}
            />
          </FormField>
        </div>

        <div>
          <span className="mb-1 block text-sm text-[var(--muted-foreground)]">Shocks</span>
          <div className="space-y-2">
            {fields.map((field, i) => {
              const rowErrors = Array.isArray(shockErrors) ? shockErrors[i] : undefined;
              const factorErr = rowErrors?.factor?.message;
              const valueErr = rowErrors?.value?.message;
              return (
                <div key={field.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Factor (e.g. SPX)"
                      className="w-40 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)]"
                      {...form.register(`shocks.${i}.factor` as const)}
                    />
                    <input
                      type="number"
                      step="any"
                      placeholder="Shock (e.g. -10)"
                      className="w-32 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm font-mono outline-none focus:border-[var(--ring)]"
                      {...form.register(`shocks.${i}.value` as const)}
                    />
                    <button
                      type="button"
                      onClick={() => remove(i)}
                      disabled={fields.length === 1}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-30"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  {(factorErr || valueErr) && (
                    <p className="pl-1 text-xs text-[var(--destructive)]">
                      {factorErr || valueErr}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          {shockErrors && !Array.isArray(shockErrors) && shockErrors.message && (
            <p className="mt-1 text-xs text-[var(--destructive)]">{shockErrors.message}</p>
          )}
          <button
            type="button"
            onClick={() => append({ factor: "", value: "" })}
            className="mt-2 inline-flex items-center gap-1 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Shock
          </button>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-[var(--primary)] px-4 text-sm font-medium text-[var(--primary-foreground)] transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {mutation.isPending ? "Running..." : "Run Stress Test"}
          </button>
        </div>
      </form>

      {result && (
        <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3 space-y-2">
          <div className="flex items-baseline justify-between">
            <h4 className="text-sm font-semibold">{result.scenario_name}</h4>
            <div className="flex gap-2 text-sm">
              <span className={`font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}>
                PnL: {fmtCurrency(result.total_pnl_impact)}
              </span>
              <span className={`font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}>
                {fmtPct(result.total_pct_change)}
              </span>
            </div>
          </div>

          {result.position_impacts.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-[var(--border)]">
              <table className="min-w-full divide-y divide-[var(--border)] text-sm">
                <thead>
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                      Instrument
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                      Current
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                      Stressed
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                      PnL Impact
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                      % Change
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--table-border)]">
                  {result.position_impacts.map((impact) => {
                    const impactPnl = parseFloat(impact.pnl_impact);
                    return (
                      <tr
                        key={impact.instrument_id}
                      >
                        <td className="px-3 py-1.5 font-medium">{impact.instrument_id}</td>
                        <td className="px-3 py-1.5 text-right font-mono">
                          {fmtCurrency(impact.current_value)}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono">
                          {fmtCurrency(impact.stressed_value)}
                        </td>
                        <td
                          className={`px-3 py-1.5 text-right font-mono ${impactPnl < 0 ? "text-[var(--destructive)]" : ""}`}
                        >
                          {fmtCurrency(impact.pnl_impact)}
                        </td>
                        <td
                          className={`px-3 py-1.5 text-right font-mono ${impactPnl < 0 ? "text-[var(--destructive)]" : ""}`}
                        >
                          {fmtPct(impact.pct_change)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
