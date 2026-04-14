"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { createInvestor } from "../api";

interface Props {
  onClose: () => void;
}

const ENTITY_TYPES = [
  { value: "individual", label: "Individual" },
  { value: "institution", label: "Institution" },
  { value: "fund_of_funds", label: "Fund of Funds" },
  { value: "family_office", label: "Family Office" },
  { value: "sovereign_wealth", label: "Sovereign Wealth" },
  { value: "endowment", label: "Endowment" },
  { value: "pension", label: "Pension" },
];

export function CreateInvestorDialog({ onClose }: Props) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState("individual");
  const [email, setEmail] = useState("");
  const [taxId, setTaxId] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createInvestor(fundSlug, {
        name,
        entity_type: entityType,
        contact_email: email || undefined,
        tax_jurisdiction: taxId || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["investors"] });
      toast.success(`Investor "${name}" added`);
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const canSubmit = name.trim().length > 0 && entityType && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Add Investor</h2>
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
          <label
            htmlFor="ci-name"
            className="block text-xs font-medium text-[var(--muted-foreground)] mb-1"
          >
            Name
          </label>
          <input
            id="ci-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Investor name"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          />
        </div>

        {/* Entity Type */}
        <div className="mb-4">
          <label
            htmlFor="ci-entity-type"
            className="block text-xs font-medium text-[var(--muted-foreground)] mb-1"
          >
            Entity Type
          </label>
          <select
            id="ci-entity-type"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          >
            {ENTITY_TYPES.map((et) => (
              <option key={et.value} value={et.value}>
                {et.label}
              </option>
            ))}
          </select>
        </div>

        {/* Email */}
        <div className="mb-4">
          <label
            htmlFor="ci-email"
            className="block text-xs font-medium text-[var(--muted-foreground)] mb-1"
          >
            Email
          </label>
          <input
            id="ci-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Optional"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          />
        </div>

        {/* Tax ID */}
        <div className="mb-4">
          <label
            htmlFor="ci-tax-id"
            className="block text-xs font-medium text-[var(--muted-foreground)] mb-1"
          >
            Tax ID
          </label>
          <input
            id="ci-tax-id"
            type="text"
            value={taxId}
            onChange={(e) => setTaxId(e.target.value)}
            placeholder="Optional"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          />
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
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Adding..." : "Add Investor"}
          </button>
        </div>
      </div>
    </div>
  );
}
