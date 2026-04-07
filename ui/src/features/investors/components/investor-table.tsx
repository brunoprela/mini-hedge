"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { capitalAccountsQueryOptions, investorsQueryOptions } from "@/features/investors/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function InvestorTable() {
  const { fundSlug } = useFundContext();
  const { data: investors, isLoading: investorsLoading } = useQuery(
    investorsQueryOptions(fundSlug),
  );
  const { data: accounts } = useQuery(capitalAccountsQueryOptions(fundSlug));

  if (investorsLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading investors...</p>;
  }

  if (!investors?.length) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-8 text-center text-sm text-[var(--muted-foreground)]">
        No investors found. Capital accounts will appear here after subscriptions are processed.
      </div>
    );
  }

  // Build a map from investor_id → capital account
  const accountMap = new Map(accounts?.map((a) => [a.investor_id, a]));

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Investor
            </th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">Type</th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              Ending Capital
            </th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              Ownership
            </th>
            <th className="px-4 py-3 text-right font-medium text-[var(--muted-foreground)]">
              Shares
            </th>
          </tr>
        </thead>
        <tbody>
          {investors.map((inv) => {
            const account = accountMap.get(inv.id);
            return (
              <tr
                key={inv.id}
                className="border-b border-[var(--border)] transition-colors hover:bg-[var(--table-row-hover)]"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/${fundSlug}/investors/${inv.id}`}
                    className="font-medium text-[var(--primary)] hover:underline"
                  >
                    {inv.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)]">
                  <span className="rounded-full bg-[var(--badge-bg)] px-2 py-0.5 text-xs">
                    {inv.entity_type.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {account ? fmt(account.ending_capital) : "-"}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {account ? pct(account.ownership_pct) : "-"}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {account ? Number(account.shares_held).toLocaleString() : "-"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function fmt(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function pct(v: string): string {
  const n = parseFloat(v) * 100;
  if (Number.isNaN(n)) return v;
  return `${n.toFixed(2)}%`;
}
