"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cashBalancesQueryOptions } from "../api";

const currencyFormatter = (currency: string) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

function fmt(value: string, currency: string): string {
  return currencyFormatter(currency).format(Number(value));
}

export function CashDashboard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: balances, isLoading } = useQuery(cashBalancesQueryOptions(fundSlug, portfolioId));

  if (isLoading || !balances) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading cash balances...</div>;
  }

  if (balances.length === 0) {
    return <div className="text-sm text-[var(--muted-foreground)]">No cash balances found.</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {balances.map((b) => (
        <div key={b.currency} className="rounded-lg border border-[var(--border)] p-4">
          <p className="text-sm font-medium">{b.currency}</p>
          <div className="mt-3 space-y-2">
            <Row label="Available" value={fmt(b.available_balance, b.currency)} />
            <Row label="Pending In" value={fmt(b.pending_inflows, b.currency)} positive />
            <Row label="Pending Out" value={fmt(b.pending_outflows, b.currency)} negative />
            <div className="border-t border-[var(--border)] pt-2">
              <Row label="Total" value={fmt(b.total_balance, b.currency)} bold />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Row({
  label,
  value,
  positive,
  negative,
  bold,
}: {
  label: string;
  value: string;
  positive?: boolean;
  negative?: boolean;
  bold?: boolean;
}) {
  let valueClass = "font-mono text-sm";
  if (positive) valueClass += " text-[var(--success)]";
  else if (negative) valueClass += " text-[var(--destructive)]";
  if (bold) valueClass += " font-semibold";

  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <span className={valueClass}>{value}</span>
    </div>
  );
}
