"use client";

import { DialogTitle, FormField, Modal } from "@mini-hedge/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFieldArray } from "react-hook-form";
import { toast } from "sonner";
import { createBlockAllocation } from "@/features/orders/api";
import type { CreateBlockAllocationRequest } from "@/features/orders/types";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useForm, z, zodResolver } from "@/shared/lib/forms";

interface BlockAllocationDialogProps {
  open: boolean;
  onClose: () => void;
}

/* ------------------------------------------------------------------ */
/*  Schema                                                             */
/* ------------------------------------------------------------------ */

const legSchema = z.object({
  portfolio_id: z.string().min(1, "Select a portfolio"),
  target_pct: z
    .string()
    .trim()
    .min(1, "Required")
    .refine((v) => {
      const n = parseFloat(v);
      return !Number.isNaN(n) && n > 0 && n <= 100;
    }, "Must be between 0 and 100"),
});

const blockAllocationSchema = z
  .object({
    instrumentId: z.string().trim().min(1, "Instrument ID is required"),
    side: z.enum(["buy", "sell"]),
    totalQuantity: z
      .string()
      .trim()
      .min(1, "Total quantity is required")
      .refine((v) => {
        const n = parseFloat(v);
        return !Number.isNaN(n) && n > 0;
      }, "Must be greater than 0"),
    orderType: z.enum(["market", "limit"]),
    limitPrice: z.string().optional(),
    legs: z.array(legSchema).min(1, "Add at least one leg"),
  })
  .superRefine((data, ctx) => {
    if (data.orderType === "limit") {
      const n = parseFloat(data.limitPrice ?? "");
      if (Number.isNaN(n) || n <= 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Limit price must be greater than 0",
          path: ["limitPrice"],
        });
      }
    }
    const sum = data.legs.reduce((acc, l) => acc + (parseFloat(l.target_pct) || 0), 0);
    if (Math.abs(sum - 100) > 0.01) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Allocations must sum to 100% (currently ${sum.toFixed(1)}%)`,
        path: ["legs"],
      });
    }
  });

type BlockAllocationValues = z.infer<typeof blockAllocationSchema>;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function BlockAllocationDialog({ open, onClose }: BlockAllocationDialogProps) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  const form = useForm<BlockAllocationValues>({
    resolver: zodResolver(blockAllocationSchema),
    defaultValues: {
      instrumentId: "",
      side: "buy",
      totalQuantity: "",
      orderType: "market",
      limitPrice: "",
      legs: [{ portfolio_id: "", target_pct: "" }],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "legs",
  });

  const orderType = form.watch("orderType");
  const side = form.watch("side");
  const legs = form.watch("legs");
  const legPctTotal = legs.reduce((sum, leg) => sum + (parseFloat(leg.target_pct) || 0), 0);

  const mutation = useMutation({
    mutationFn: (request: CreateBlockAllocationRequest) => createBlockAllocation(fundSlug, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      toast.success("Block allocation created successfully");
      form.reset();
      onClose();
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to create block allocation");
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    const request: CreateBlockAllocationRequest = {
      instrument_id: values.instrumentId,
      side: values.side,
      total_quantity: parseFloat(values.totalQuantity),
      order_type: values.orderType,
      ...(values.orderType === "limit"
        ? { limit_price: parseFloat(values.limitPrice ?? "0") }
        : {}),
      legs: values.legs.map((leg) => ({
        fund_slug: fundSlug,
        portfolio_id: leg.portfolio_id,
        target_pct: parseFloat(leg.target_pct) / 100,
      })),
    };
    mutation.mutate(request);
  });

  const legsError = form.formState.errors.legs;
  const legsMessage =
    legsError && !Array.isArray(legsError) && "message" in legsError
      ? legsError.message
      : undefined;

  return (
    <Modal open={open} onClose={onClose}>
      <div className="mb-4 flex items-center justify-between">
        <DialogTitle className="text-sm font-semibold text-[var(--foreground-bright)]">
          Block Allocation
        </DialogTitle>
      </div>

      <form onSubmit={onSubmit} className="space-y-3">
        {/* Instrument ID */}
        <FormField
          label="Instrument ID"
          required
          error={form.formState.errors.instrumentId?.message}
        >
          <input
            id="block-instrument-id"
            type="text"
            placeholder="e.g. AAPL"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            {...form.register("instrumentId")}
          />
        </FormField>

        {/* Side */}
        <div>
          <span className="mb-1 block text-sm font-medium">Side</span>
          <div className="flex gap-1 rounded-md border border-[var(--border)] p-0.5">
            <button
              type="button"
              onClick={() => form.setValue("side", "buy")}
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
              onClick={() => form.setValue("side", "sell")}
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
        <FormField
          label="Total Quantity"
          required
          error={form.formState.errors.totalQuantity?.message}
        >
          <input
            id="block-total-quantity"
            type="number"
            min="0"
            step="any"
            placeholder="0"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            {...form.register("totalQuantity")}
          />
        </FormField>

        {/* Order Type */}
        <FormField
          label="Order Type"
          required
          error={form.formState.errors.orderType?.message}
        >
          <select
            id="block-order-type"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            {...form.register("orderType")}
          >
            <option value="market">Market</option>
            <option value="limit">Limit</option>
          </select>
        </FormField>

        {/* Limit Price */}
        {orderType === "limit" && (
          <FormField
            label="Limit Price"
            required
            error={form.formState.errors.limitPrice?.message}
          >
            <input
              id="block-limit-price"
              type="number"
              min="0"
              step="any"
              placeholder="0.00"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              {...form.register("limitPrice")}
            />
          </FormField>
        )}

        {/* Allocation Legs */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">Allocation Legs</span>
            <button
              type="button"
              onClick={() => append({ portfolio_id: "", target_pct: "" })}
              className="text-sm text-[var(--primary)] hover:underline"
            >
              Add Portfolio
            </button>
          </div>
          <div className="space-y-2">
            {fields.map((field, index) => {
              const rowErrors = Array.isArray(legsError) ? legsError[index] : undefined;
              const portfolioErr = rowErrors?.portfolio_id?.message;
              const pctErr = rowErrors?.target_pct?.message;
              return (
                <div key={field.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <select
                      className="flex-1 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                      {...form.register(`legs.${index}.portfolio_id` as const)}
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
                      min="0"
                      max="100"
                      step="any"
                      placeholder="%"
                      className="w-28 rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                      {...form.register(`legs.${index}.target_pct` as const)}
                    />
                    {fields.length > 1 && (
                      <button
                        type="button"
                        onClick={() => remove(index)}
                        className="text-sm text-[var(--destructive)] hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  {(portfolioErr || pctErr) && (
                    <p className="pl-1 text-xs text-[var(--destructive)]">
                      {portfolioErr || pctErr}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          {legsMessage && (
            <p className="mt-1 text-xs text-[var(--destructive)]">{legsMessage}</p>
          )}
          {!legsMessage && legPctTotal > 0 && Math.abs(legPctTotal - 100) > 0.01 && (
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              Current total: {legPctTotal.toFixed(1)}%
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
            disabled={mutation.isPending}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Creating..." : "Create Allocation"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
