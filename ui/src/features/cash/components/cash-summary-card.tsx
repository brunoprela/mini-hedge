"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { InfoTooltip } from "@/shared/components/table-controls";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cashBalancesQueryOptions, settlementsQueryOptions } from "../api";

export function CashSummaryCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: balances, isLoading: balancesLoading } = useQuery(
    cashBalancesQueryOptions(fundSlug, portfolioId),
  );
  const { data: settlements, isLoading: settlementsLoading } = useQuery(
    settlementsQueryOptions(fundSlug, portfolioId),
  );

  const isLoading = balancesLoading || settlementsLoading;

  if (isLoading) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="text-sm text-[var(--muted-foreground)]">Loading cash summary...</p>
      </div>
    );
  }

  const totalAvailable = (balances ?? []).reduce((sum, b) => sum + Number(b.available_balance), 0);

  const pendingCount = (settlements ?? []).filter((s) => s.status === "pending").length;

  const fmtTotal = totalAvailable.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
        Cash Available
        <InfoTooltip text="Total cash available for trading across all currencies" />
      </p>
      <p className="mt-1 font-mono text-lg font-semibold">{fmtTotal}</p>
      <p className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
        {pendingCount} pending settlement{pendingCount !== 1 ? "s" : ""}
        <InfoTooltip text="Trades awaiting T+2 settlement that will affect cash balance" />
      </p>
      <Link
        href={`/${fundSlug}/cash`}
        className="mt-2 inline-block text-xs font-medium text-[var(--primary)] hover:underline"
      >
        View details &rarr;
      </Link>
    </div>
  );
}
