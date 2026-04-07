"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  investorHistoryQueryOptions,
  investorTransactionsQueryOptions,
} from "@/features/investors/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function InvestorDetail({ investorId }: { investorId: string }) {
  const { fundSlug } = useFundContext();
  const { data: history, isLoading: historyLoading } = useQuery(
    investorHistoryQueryOptions(fundSlug, investorId),
  );
  const { data: transactions } = useQuery(investorTransactionsQueryOptions(fundSlug, investorId));

  const latest = history?.[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Link
          href={`/${fundSlug}/investors`}
          className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          Investors
        </Link>
        <span className="text-sm text-[var(--muted-foreground)]">/</span>
        <h1 className="text-2xl font-semibold">{latest?.investor_name ?? "Investor"}</h1>
      </div>

      {historyLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>}

      {latest && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Ending Capital" value={fmt(latest.ending_capital)} />
          <StatCard label="Ownership" value={pct(latest.ownership_pct)} />
          <StatCard label="Shares Held" value={Number(latest.shares_held).toLocaleString()} />
          <StatCard label="Share Class" value={latest.share_class} />
        </div>
      )}

      {/* Capital Account History */}
      {history && history.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Capital History</h2>
          <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                  <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">
                    Date
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    Beginning
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    Contributions
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    P&L
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    Fees
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    Ending
                  </th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-[var(--border)] transition-colors hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-2">{row.effective_date}</td>
                    <td className="px-3 py-2 text-right font-mono">{fmt(row.beginning_capital)}</td>
                    <td className="px-3 py-2 text-right font-mono">{fmt(row.contributions)}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {fmtSigned(row.pnl_allocation)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {fmt(row.management_fee_allocation)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono font-semibold">
                      {fmt(row.ending_capital)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Transactions */}
      {transactions && transactions.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Transactions</h2>
          <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                  <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">
                    Date
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">
                    Type
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    Amount
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    Shares
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">
                    NAV/Share
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">
                    Notes
                  </th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr
                    key={tx.id}
                    className="border-b border-[var(--border)] transition-colors hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-2">{tx.business_date}</td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-[var(--badge-bg)] px-2 py-0.5 text-xs">
                        {tx.transaction_type.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{fmt(tx.amount)}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {Number(tx.shares).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{fmt(tx.nav_per_share)}</td>
                    <td className="px-3 py-2 text-[var(--muted-foreground)]">{tx.notes ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-[var(--foreground-bright)]">
        {value}
      </p>
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

function fmtSigned(v: string): string {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return v;
  const formatted = Math.abs(n).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  if (n > 0) return `+${formatted}`;
  if (n < 0) return `-${formatted}`;
  return formatted;
}

function pct(v: string): string {
  const n = parseFloat(v) * 100;
  if (Number.isNaN(n)) return v;
  return `${n.toFixed(2)}%`;
}
