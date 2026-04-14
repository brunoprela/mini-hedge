"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api";

interface FundInfo {
  fund_slug: string;
  fund_name: string;
  role: string;
  customer_id?: string | null;
  customer_name?: string | null;
}

export function useFunds() {
  return useQuery({
    queryKey: ["my-funds"],
    queryFn: async () => {
      const funds = await apiFetch<FundInfo[]>("me/funds");
      // Normalize to FundDetail-like shape for downstream consumers
      return {
        items: funds.map((f) => ({
          slug: f.fund_slug,
          name: f.fund_name,
          base_currency: "USD",
        })),
        total: funds.length,
        limit: funds.length,
        offset: 0,
      };
    },
  });
}

export function FundSelector({
  funds,
  value,
  onChange,
}: {
  funds: { slug: string; name: string }[];
  value: string;
  onChange: (slug: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
    >
      {funds.map((f) => (
        <option key={f.slug} value={f.slug}>
          {f.name}
        </option>
      ))}
    </select>
  );
}
