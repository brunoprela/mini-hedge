"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import {
  investorHistoryQueryOptions,
  investorTransactionsQueryOptions,
} from "@/features/investors/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { CapitalActionDialog } from "./capital-action-dialog";

type Tab = "overview" | "history" | "transactions";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "history", label: "Capital History" },
  { id: "transactions", label: "Transactions" },
];

export function InvestorDetail({ investorId }: { investorId: string }) {
  const { fundSlug } = useFundContext();
  const { data: history, isLoading: historyLoading } = useQuery(
    investorHistoryQueryOptions(fundSlug, investorId),
  );
  const { data: transactions } = useQuery(investorTransactionsQueryOptions(fundSlug, investorId));

  const latest = history?.[0];
  const [capitalAction, setCapitalAction] = useState<"subscription" | "redemption" | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Link
          href={`/${fundSlug}/investors`}
          className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          Investors
        </Link>
        <span className="text-sm text-[var(--muted-foreground)]">/</span>
        <h1 className="text-sm font-semibold">{latest?.investor_name ?? "Investor"}</h1>
        <span className="ml-auto flex items-center gap-2 text-sm">
          <button
            type="button"
            onClick={() => setCapitalAction("subscription")}
            className="rounded-md bg-[var(--success)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:brightness-110"
          >
            Subscription
          </button>
          <button
            type="button"
            onClick={() => setCapitalAction("redemption")}
            className="rounded-md bg-[var(--destructive)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:brightness-110"
          >
            Redemption
          </button>
          <Link
            href={`/${fundSlug}/cash`}
            className="text-[var(--muted-foreground)] underline-offset-2 hover:text-[var(--foreground)] hover:underline"
          >
            View Fund Cash →
          </Link>
        </span>
      </div>

      {capitalAction && (
        <CapitalActionDialog
          investorId={investorId}
          investorName={latest?.investor_name ?? "Investor"}
          actionType={capitalAction}
          onClose={() => setCapitalAction(null)}
        />
      )}

      {historyLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "overview" && latest && (
        <div className="space-y-3">
          {/* Hero KPI */}
          <div className="flex items-baseline gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Ending Capital</p>
              <p className="font-mono text-base font-bold">{fmt(latest.ending_capital)}</p>
            </div>
            <div className="h-8 w-px bg-[var(--border)]" />
            <div className="flex flex-1 gap-3">
              <StatCard label="Ownership" value={pct(latest.ownership_pct)} />
              <StatCard label="Shares Held" value={Number(latest.shares_held).toLocaleString()} />
              <StatCard label="Share Class" value={latest.share_class} />
            </div>
          </div>

          {/* Recent history preview */}
          {history && history.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-[var(--border)]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                    <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">Date</th>
                    <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Beginning</th>
                    <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">P&L</th>
                    <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Ending</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 5).map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-[var(--border)] transition-colors hover:bg-[var(--table-row-hover)]"
                    >
                      <td className="px-3 py-2">{row.effective_date}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmt(row.beginning_capital)}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtSigned(row.pnl_allocation)}</td>
                      <td className="px-3 py-2 text-right font-mono font-semibold">{fmt(row.ending_capital)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === "history" && history && history.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">Date</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Beginning</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Contributions</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">P&L</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Fees</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Ending</th>
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
                  <td className="px-3 py-2 text-right font-mono">{fmtSigned(row.pnl_allocation)}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(row.management_fee_allocation)}</td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">{fmt(row.ending_capital)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "transactions" && transactions && transactions.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">Date</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">Type</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Amount</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">Shares</th>
                <th className="px-3 py-2 text-right font-medium text-[var(--muted-foreground)]">NAV/Share</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--muted-foreground)]">Notes</th>
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
                  <td className="px-3 py-2 text-right font-mono">{Number(tx.shares).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(tx.nav_per_share)}</td>
                  <td className="px-3 py-2 text-[var(--muted-foreground)]">{tx.notes ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold text-[var(--foreground-bright)]">
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
