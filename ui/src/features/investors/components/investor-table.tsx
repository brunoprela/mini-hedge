"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { capitalAccountsQueryOptions, investorsQueryOptions } from "@/features/investors/api";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function InvestorTable() {
  const { fundSlug } = useFundContext();
  const { data: investors, isLoading: investorsLoading } = useQuery(
    investorsQueryOptions(fundSlug),
  );
  const { data: accounts } = useQuery(capitalAccountsQueryOptions(fundSlug));
  const exportCSV = useExportCSV();

  const handleExport = () => {
    if (!investors || investors.length === 0) return;
    const accountMap = new Map(accounts?.map((a) => [a.investor_id, a]));
    const exportData = investors.map((inv) => {
      const account = accountMap.get(inv.id);
      return {
        name: inv.name,
        entity_type: inv.entity_type,
        tax_jurisdiction: inv.tax_jurisdiction ?? "",
        contact_email: inv.contact_email ?? "",
        is_active: inv.is_active,
        ending_capital: account?.ending_capital ?? "",
        ownership_pct: account?.ownership_pct ?? "",
        shares_held: account?.shares_held ?? "",
      };
    });
    exportCSV(exportData as unknown as Record<string, unknown>[], "investors");
  };

  if (investorsLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading investors...</p>;
  }

  if (!investors?.length) {
    return (
      <div className="rounded-md border border-[var(--border)] p-8 text-center text-sm text-[var(--muted-foreground)]">
        No investors found. Capital accounts will appear here after subscriptions are processed.
      </div>
    );
  }

  // Build a map from investor_id → capital account
  const accountMap = new Map(accounts?.map((a) => [a.investor_id, a]));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={handleExport}
          title="Export to CSV"
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
        >
          <Download className="h-4 w-4" />
          CSV
        </button>
      </div>
      <div className="overflow-x-auto rounded-md border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
              Investor
            </th>
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
              Type
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              Ending Capital
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              Ownership
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
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
                <td className="px-3 py-1.5">
                  <Link
                    href={`/${fundSlug}/investors/${inv.id}`}
                    className="font-medium text-[var(--primary)] hover:underline"
                  >
                    {inv.name}
                  </Link>
                </td>
                <td className="px-3 py-1.5 text-[var(--muted-foreground)]">
                  <span className="rounded-full bg-[var(--badge-bg)] px-2 py-0.5 text-xs">
                    {inv.entity_type.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {account ? fmt(account.ending_capital) : "-"}
                </td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {account ? pct(account.ownership_pct) : "-"}
                </td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {account ? Number(account.shares_held).toLocaleString() : "-"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
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
