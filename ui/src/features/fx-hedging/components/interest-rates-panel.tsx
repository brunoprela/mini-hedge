"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { fxInterestRatesQueryOptions } from "../api";

export function InterestRatesPanel() {
  const { fundSlug } = useFundContext();
  const { data: rates, isLoading } = useQuery(fxInterestRatesQueryOptions(fundSlug));

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading rates...</div>;
  }

  if (!rates || rates.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        No interest rate data available.
      </div>
    );
  }

  // Group by currency, show latest rate per currency
  const byCurrency = new Map<string, typeof rates>();
  for (const r of rates) {
    const existing = byCurrency.get(r.currency) ?? [];
    existing.push(r);
    byCurrency.set(r.currency, existing);
  }

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from(byCurrency.entries()).map(([ccy, ccyRates]) => {
        const sorted = ccyRates.sort((a, b) => a.tenor_days - b.tenor_days);
        const shortRate = sorted[0];
        return (
          <div key={ccy} className="rounded-lg border border-[var(--border)] p-3">
            <p className="text-sm font-semibold">{ccy}</p>
            <p className="mt-1 text-lg tabular-nums">
              {(Number(shortRate.rate) * 100).toFixed(2)}%
            </p>
            <p className="text-xs text-[var(--muted-foreground)]">{shortRate.tenor_days}d rate</p>
          </div>
        );
      })}
    </div>
  );
}
