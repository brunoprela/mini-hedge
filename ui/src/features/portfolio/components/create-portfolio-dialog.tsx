"use client";

import { FormField } from "@mini-hedge/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { createPortfolio } from "../api";

interface Props {
  onClose: () => void;
}

/* ------------------------------------------------------------------ */
/*  Schema                                                             */
/* ------------------------------------------------------------------ */

const BASE_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF"] as const;

const createPortfolioSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Name is required")
    .max(80, "Name must be 80 characters or fewer"),
  strategy: z
    .string()
    .trim()
    .max(80, "Strategy must be 80 characters or fewer")
    .optional(),
  base_currency: z.enum(BASE_CURRENCIES),
});

type CreatePortfolioValues = z.infer<typeof createPortfolioSchema>;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CreatePortfolioDialog({ onClose }: Props) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const form = useForm<CreatePortfolioValues>({
    resolver: zodResolver(createPortfolioSchema),
    defaultValues: {
      name: "",
      strategy: "",
      base_currency: "USD",
    },
  });

  const mutation = useMutation({
    mutationFn: (values: CreatePortfolioValues) =>
      createPortfolio(fundSlug, {
        name: values.name,
        strategy: values.strategy || undefined,
        base_currency: values.base_currency,
      }),
    onSuccess: (_data, values) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      toast.success(`Portfolio "${values.name}" created`);
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const onSubmit = form.handleSubmit((values) => mutation.mutate(values));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Create Portfolio</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        {/* Name */}
        <div className="mb-4">
          <FormField
            label="Name"
            required
            error={form.formState.errors.name?.message}
          >
            <input
              id="cp-name"
              type="text"
              placeholder="Portfolio name"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              {...form.register("name")}
            />
          </FormField>
        </div>

        {/* Strategy */}
        <div className="mb-4">
          <FormField
            label="Strategy"
            error={form.formState.errors.strategy?.message}
          >
            <input
              id="cp-strategy"
              type="text"
              placeholder="e.g. Long/Short Equity"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              {...form.register("strategy")}
            />
          </FormField>
        </div>

        {/* Base Currency */}
        <div className="mb-4">
          <FormField
            label="Base Currency"
            required
            error={form.formState.errors.base_currency?.message}
          >
            <select
              id="cp-currency"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              {...form.register("base_currency")}
            >
              {BASE_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FormField>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-[var(--border)] px-4 py-1.5 text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Creating..." : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
