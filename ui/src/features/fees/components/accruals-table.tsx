"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cn } from "@/shared/lib/cn";
import { feeAccrualsQueryOptions } from "../api";

function fmtAmount(value: string): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

const TYPE_STYLES: Record<string, string> = {
  management: "bg-blue-400/10 text-blue-400",
  performance: "bg-purple-400/10 text-purple-400",
};

export function AccrualsTable({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: accruals, isLoading } = useQuery(feeAccrualsQueryOptions(fundSlug, portfolioId));

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading accruals...</div>;
  }

  if (!accruals || accruals.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        No fee accruals found. Accruals are created during the EOD process.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--card)]">
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">Date</th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">Type</th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              NAV Basis
            </th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              Accrued
            </th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              Cumulative
            </th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {accruals.map((a, i) => (
            <tr
              key={a.id ?? i}
              className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--sidebar-active)]"
            >
              <td className="px-4 py-3">{a.accrual_date}</td>
              <td className="px-4 py-3">
                <span
                  className={cn(
                    "inline-block rounded px-1.5 py-0.5 text-xs font-medium",
                    TYPE_STYLES[a.fee_type] ?? "",
                  )}
                >
                  {a.fee_type}
                </span>
              </td>
              <td className="px-4 py-3 text-right tabular-nums">{fmtAmount(a.nav_basis)}</td>
              <td className="px-4 py-3 text-right tabular-nums">{fmtAmount(a.accrued_amount)}</td>
              <td className="px-4 py-3 text-right tabular-nums">
                {fmtAmount(a.cumulative_amount)}
              </td>
              <td className="px-4 py-3 text-xs text-[var(--muted-foreground)]">{a.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
