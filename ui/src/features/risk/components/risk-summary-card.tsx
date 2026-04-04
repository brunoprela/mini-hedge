"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { InfoTooltip } from "@/shared/components/table-controls";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { riskSnapshotQueryOptions } from "../api";

function fmtCurrency(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function RiskSummaryCard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: snapshot, isLoading } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--muted-foreground)]">Risk</h3>
        <Link
          href={`/${fundSlug}/risk`}
          className="text-xs text-[var(--muted-foreground)] hover:underline"
        >
          View details &rarr;
        </Link>
      </div>

      {isLoading && <p className="mt-2 text-xs text-[var(--muted-foreground)]">Loading...</p>}

      {!isLoading && !snapshot && (
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">No snapshot</p>
      )}

      {snapshot && (
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <p className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
              VaR 95% (1d)
              <InfoTooltip text="Maximum expected daily loss at 95% confidence" />
            </p>
            <p className="font-mono text-sm font-semibold">{fmtCurrency(snapshot.var_95_1d)}</p>
          </div>
          <div>
            <p className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
              VaR 99% (1d)
              <InfoTooltip text="Maximum expected daily loss at 99% confidence" />
            </p>
            <p className="font-mono text-sm font-semibold">{fmtCurrency(snapshot.var_99_1d)}</p>
          </div>
        </div>
      )}
    </div>
  );
}
