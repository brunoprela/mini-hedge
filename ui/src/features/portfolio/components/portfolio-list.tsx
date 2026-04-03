"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { portfoliosQueryOptions } from "../api";

export function PortfolioList() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading portfolios...</p>;
  }

  if (!portfolios || portfolios.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No portfolios found.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {portfolios.map((p) => (
        <Link
          key={p.id}
          href={`/${fundSlug}/portfolio/${p.id}`}
          className="rounded-lg border border-[var(--border)] p-4 transition-colors hover:bg-[var(--muted)]"
        >
          <h3 className="font-medium">{p.name}</h3>
          <p className="text-sm text-[var(--muted-foreground)]">{p.strategy ?? "No strategy"}</p>
        </Link>
      ))}
    </div>
  );
}
