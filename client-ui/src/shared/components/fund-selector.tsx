"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/lib/api-client";

export function useFunds() {
  return useQuery({
    queryKey: ["my-funds"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/me/funds");
      if (error) throw error;
      const funds = data ?? [];
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
      className="w-full sm:w-auto max-w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--foreground)] min-h-11 focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
    >
      {funds.map((f) => (
        <option key={f.slug} value={f.slug}>
          {f.name}
        </option>
      ))}
    </select>
  );
}
