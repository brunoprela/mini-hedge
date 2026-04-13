"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api";
import type { FundDetail, FundPage } from "@/shared/types";

export function useFunds() {
  return useQuery({
    queryKey: ["funds"],
    queryFn: () => apiFetch<FundPage>("admin/funds?limit=100"),
  });
}

export function FundSelector({
  funds,
  value,
  onChange,
}: {
  funds: FundDetail[];
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
