"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/shared/components/error-state";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";

interface StatementRecord {
  id: string;
  investor_id: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  status: string;
}

interface LetterRecord {
  id: string;
  year: number;
  month: number;
  fund_nav: string;
  fund_return: string;
  generated_at: string;
}

type Tab = "statements" | "letters";

function fmtUSD(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export default function ClientReportingPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("statements");

  const statementsQuery = useQuery({
    queryKey: ["client-reporting", "statements", fundSlug],
    queryFn: () =>
      apiFetch<StatementRecord[]>(
        `funds/${fundSlug}/regulatory/investor-statements`,
      ),
    enabled: !!fundSlug && activeTab === "statements",
  });

  const lettersQuery = useQuery({
    queryKey: ["client-reporting", "letters", fundSlug],
    queryFn: () =>
      apiFetch<LetterRecord[]>(
        `funds/${fundSlug}/regulatory/performance-letters`,
      ),
    enabled: !!fundSlug && activeTab === "letters",
  });

  const generateStatement = useMutation({
    mutationFn: () =>
      apiFetch(`funds/${fundSlug}/regulatory/generate-investor-statement`, {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["client-reporting", "statements"],
      });
      toast.success("Investor statement generated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const generateLetter = useMutation({
    mutationFn: () =>
      apiFetch(`funds/${fundSlug}/regulatory/generate-performance-letter`, {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["client-reporting", "letters"],
      });
      toast.success("Performance letter generated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const statements = statementsQuery.data ?? [];
  const letters = lettersQuery.data ?? [];

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Client Reporting</h2>

      <div className="mb-6">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
          showPortfolio={false}
        />
      </div>

      {!fundSlug ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund to manage client reporting.
        </p>
      ) : (
        <>
          {/* Tabs */}
          <div className="mb-4 flex gap-4 border-b border-[var(--border)]">
            {(["statements", "letters"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`pb-2 text-sm font-medium capitalize ${
                  activeTab === tab
                    ? "border-b-2 border-[var(--primary)] text-[var(--foreground)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Statements tab */}
          {activeTab === "statements" && (
            <>
              <div className="mb-4">
                <button
                  type="button"
                  disabled={generateStatement.isPending}
                  onClick={() => generateStatement.mutate()}
                  className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
                >
                  {generateStatement.isPending && (
                    <Loader2 size={14} className="animate-spin" />
                  )}
                  Generate Statement
                </button>
              </div>

              {statementsQuery.isLoading ? (
                <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
                  Loading...
                </p>
              ) : statementsQuery.isError ? (
                <ErrorState
                  message={statementsQuery.error.message}
                  onRetry={() => statementsQuery.refetch()}
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-[var(--border)]">
                    <thead>
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Investor</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Period</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Generated At</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--table-border)]">
                      {statements.map((row) => (
                        <tr
                          key={row.id}
                          className="transition-colors hover:bg-[var(--table-row-hover)]"
                        >
                          <td className="px-3 py-2 text-sm">
                            {row.investor_id}
                          </td>
                          <td className="px-3 py-2 text-sm font-mono">
                            {row.period_start} &mdash; {row.period_end}
                          </td>
                          <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                            {new Date(row.generated_at).toLocaleString()}
                          </td>
                          <td className="px-3 py-2 text-sm">
                            <StatusBadge
                              label={row.status}
                              variant={
                                row.status === "completed"
                                  ? "success"
                                  : row.status === "pending"
                                    ? "warning"
                                    : "neutral"
                              }
                            />
                          </td>
                        </tr>
                      ))}
                      {statements.length === 0 && (
                        <tr>
                          <td
                            colSpan={4}
                            className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]"
                          >
                            No investor statements found.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* Letters tab */}
          {activeTab === "letters" && (
            <>
              <div className="mb-4">
                <button
                  type="button"
                  disabled={generateLetter.isPending}
                  onClick={() => generateLetter.mutate()}
                  className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
                >
                  {generateLetter.isPending && (
                    <Loader2 size={14} className="animate-spin" />
                  )}
                  Generate Letter
                </button>
              </div>

              {lettersQuery.isLoading ? (
                <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
                  Loading...
                </p>
              ) : lettersQuery.isError ? (
                <ErrorState
                  message={lettersQuery.error.message}
                  onRetry={() => lettersQuery.refetch()}
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-[var(--border)]">
                    <thead>
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Period</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fund NAV</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fund Return</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Generated At</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--table-border)]">
                      {letters.map((row) => (
                        <tr
                          key={row.id}
                          className="transition-colors hover:bg-[var(--table-row-hover)]"
                        >
                          <td className="px-3 py-2 text-sm font-mono">
                            {row.year}-{String(row.month).padStart(2, "0")}
                          </td>
                          <td className="px-3 py-2 text-sm text-right font-mono">
                            {fmtUSD(row.fund_nav)}
                          </td>
                          <td className="px-3 py-2 text-sm text-right font-mono">
                            {row.fund_return}%
                          </td>
                          <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                            {new Date(row.generated_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                      {letters.length === 0 && (
                        <tr>
                          <td
                            colSpan={4}
                            className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]"
                          >
                            No performance letters found.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
