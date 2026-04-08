"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { remediationQueryOptions } from "../api";

export function RemediationPanel({ portfolioId }: { portfolioId: string; fundSlug: string }) {
  const { fundSlug } = useFundContext();
  const { data: suggestions, isLoading } = useQuery(remediationQueryOptions(fundSlug, portfolioId));

  if (isLoading) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">Loading remediation suggestions...</p>
    );
  }

  if (!suggestions || suggestions.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No remediation actions needed.</p>;
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-[var(--foreground)]">
        Suggested Remediation Trades
      </h3>
      <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
              <th className="px-3 py-1.5 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Instrument
              </th>
              <th className="px-3 py-1.5 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Side
              </th>
              <th className="px-3 py-1.5 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Quantity
              </th>
              <th className="px-3 py-1.5 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Reason
              </th>
              <th className="px-3 py-1.5 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {suggestions.map((s) => (
              <tr
                key={`${s.violation_id}-${s.instrument_id}`}
                className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
              >
                <td className="px-3 py-1.5 font-medium">{s.instrument_id}</td>
                <td className="px-3 py-1.5">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      s.side.toLowerCase() === "buy"
                        ? "bg-[var(--success)]/15 text-[var(--success)]"
                        : "bg-[var(--destructive)]/15 text-[var(--destructive)]"
                    }`}
                  >
                    {s.side}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-[var(--muted-foreground)]">{s.quantity}</td>
                <td className="px-3 py-1.5 text-[var(--muted-foreground)]">{s.reason}</td>
                <td className="px-3 py-1.5">
                  <Link
                    href={`/${fundSlug}/portfolio/${portfolioId}?tab=positions&trade_instrument=${encodeURIComponent(s.instrument_id)}&trade_side=${s.side.toLowerCase()}&trade_qty=${s.quantity}`}
                    className="text-sm text-[var(--primary)] underline-offset-2 hover:underline"
                  >
                    Send to Trade Ticket
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
