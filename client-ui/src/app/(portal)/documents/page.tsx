"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { apiFetch } from "@/shared/lib/api";
import { ErrorState } from "@/shared/components/error-state";
import { useFunds, FundSelector } from "@/shared/components/fund-selector";
import type { InvestorStatement, MonthlyPerformanceLetter } from "@/shared/types";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

type Tab = "statements" | "letters";

export default function DocumentsPage() {
  const { data: fundsPage, isLoading: fundsLoading, error: fundsError, refetch } = useFunds();
  const funds = fundsPage?.items ?? [];
  const [selectedSlug, setSelectedSlug] = useState<string>("");
  const slug = selectedSlug || funds[0]?.slug || "";
  const [tab, setTab] = useState<Tab>("statements");

  const {
    data: statements,
    isLoading: stmtsLoading,
    error: stmtsError,
  } = useQuery({
    queryKey: ["documents-statements", slug],
    queryFn: () =>
      apiFetch<InvestorStatement[]>(`funds/${slug}/regulatory/investor-statements`),
    enabled: !!slug,
  });

  const {
    data: letters,
    isLoading: lettersLoading,
    error: lettersError,
  } = useQuery({
    queryKey: ["documents-letters", slug],
    queryFn: () =>
      apiFetch<MonthlyPerformanceLetter[]>(`funds/${slug}/regulatory/performance-letters`),
    enabled: !!slug,
  });

  const isLoading = fundsLoading || (tab === "statements" ? stmtsLoading : lettersLoading);
  const error = fundsError || (tab === "statements" ? stmtsError : lettersError);

  if (error) {
    return <ErrorState message={String(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">Documents</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Statements, letters, and regulatory documents.
        </p>
      </div>

      {/* Fund Selector */}
      {funds.length > 1 && (
        <div className="flex items-center gap-2">
          <label className="text-sm text-[var(--muted-foreground)]">Fund:</label>
          <FundSelector funds={funds} value={slug} onChange={setSelectedSlug} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-[var(--muted)] p-1 w-fit">
        <button
          type="button"
          onClick={() => setTab("statements")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            tab === "statements"
              ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
        >
          Statements
        </button>
        <button
          type="button"
          onClick={() => setTab("letters")}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            tab === "letters"
              ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
        >
          Performance Letters
        </button>
      </div>

      {/* Content */}
      {!slug ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--muted)] py-16">
          <FileText size={40} className="text-[var(--muted-foreground)] mb-3" />
          <p className="text-sm text-[var(--muted-foreground)]">No funds available.</p>
        </div>
      ) : tab === "statements" ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Investor
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Share Class
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Period
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Beginning Capital
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Ending Capital
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Net Return %
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {isLoading ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    Loading...
                  </td>
                </tr>
              ) : !statements || statements.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    No statements available.
                  </td>
                </tr>
              ) : (
                statements.map((s, i) => (
                  <tr key={`${s.investor_id}-${s.period_start}-${i}`} className="hover:bg-[var(--table-row-hover)]">
                    <td className="px-4 py-3 font-medium text-[var(--foreground)]">
                      {s.investor_name}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">{s.share_class}</td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">
                      {s.period_start} to {s.period_end}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatCurrency(Number(s.beginning_capital))}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium">
                      {formatCurrency(Number(s.ending_capital))}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span
                        className={
                          Number(s.net_return_pct) >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--destructive)]"
                        }
                      >
                        {Number(s.net_return_pct) >= 0 ? "+" : ""}
                        {Number(s.net_return_pct).toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Period
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Gross Return %
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Net Return %
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Benchmark %
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Active Return %
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Total AUM
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {isLoading ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    Loading...
                  </td>
                </tr>
              ) : !letters || letters.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    No performance letters available.
                  </td>
                </tr>
              ) : (
                letters.map((l) => (
                  <tr key={`${l.fund_slug}-${l.period}`} className="hover:bg-[var(--table-row-hover)]">
                    <td className="px-4 py-3 font-medium text-[var(--foreground)]">{l.period}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {Number(l.gross_return_pct).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {Number(l.net_return_pct).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[var(--muted-foreground)]">
                      {Number(l.benchmark_return_pct).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span
                        className={
                          Number(l.active_return_pct) >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--destructive)]"
                        }
                      >
                        {Number(l.active_return_pct) >= 0 ? "+" : ""}
                        {Number(l.active_return_pct).toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatCurrency(Number(l.total_aum))}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
