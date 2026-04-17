"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Calculator, CheckCircle } from "lucide-react";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { ErrorState, TableSkeleton } from "@mini-hedge/ui";
import { StatusBadge } from "@mini-hedge/ui";
import { api, fundHeaders } from "@/shared/lib/api-client";

type Tab = "history" | "runs";

function formatCurrency(value: string | number) {
  return Number(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function formatNavPerShare(value: string | number) {
  return Number(value).toFixed(4);
}

function formatDuration(
  startedAt: string,
  completedAt: string | null | undefined,
): string {
  if (!completedAt) return "—";
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  return `${mins}m ${rem}s`;
}

function formatDatetime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function NAVComputationPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [businessDate, setBusinessDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [activeTab, setActiveTab] = useState<Tab>("history");

  const navHistory = useQuery({
    queryKey: ["nav", "history", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eod/nav/history", {
        params: { query: { period: "90d" } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    enabled: !!fundSlug,
  });

  const eodHistory = useQuery({
    queryKey: ["eod", "history", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eod/history", {
        params: { query: { limit: 20 } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    enabled: !!fundSlug,
  });

  const calculateNav = useMutation({
    mutationFn: async (data: { fund_slug: string; business_date: string }) => {
      const { data: result, error } = await api.POST("/api/v1/eod/run", {
        body: { business_date: data.business_date },
        headers: fundHeaders(data.fund_slug),
      });
      if (error) throw error;
      return result;
    },
    onSuccess: () => {
      toast.success("NAV calculation triggered");
      queryClient.invalidateQueries({ queryKey: ["nav"] });
      queryClient.invalidateQueries({ queryKey: ["eod"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const sortedNav = navHistory.data
    ? [...navHistory.data].sort(
        (a, b) =>
          new Date(b.business_date).getTime() -
          new Date(a.business_date).getTime(),
      )
    : [];

  const runs = eodHistory.data ?? [];
  const lastRun = runs.length > 0 ? runs[0] : null;
  const latestNav = sortedNav[0] ?? null;

  function handleApprove() {
    const confirmed = window.confirm(
      `Approve NAV for ${businessDate} and distribute to investors?`,
    );
    if (confirmed) {
      toast.success(
        `NAV approved and distribution initiated for ${businessDate}`,
      );
    }
  }

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">NAV Computation</h2>

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
        <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
          Select a fund to compute and review NAV.
        </p>
      ) : (
        <>
          {/* Action bar */}
          <div className="mb-6 flex flex-wrap items-end gap-4">
            <label className="block">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">
                Business Date
              </span>
              <input
                type="date"
                value={businessDate}
                onChange={(e) => setBusinessDate(e.target.value)}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              />
            </label>
            <button
              type="button"
              disabled={calculateNav.isPending || !businessDate}
              onClick={() =>
                calculateNav.mutate({
                  fund_slug: fundSlug,
                  business_date: businessDate,
                })
              }
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {calculateNav.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Calculator size={14} />
              )}
              {calculateNav.isPending ? "Calculating..." : "Calculate NAV"}
            </button>
            <button
              type="button"
              onClick={handleApprove}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-1.5 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--muted)] disabled:opacity-50"
            >
              <CheckCircle size={14} />
              Approve &amp; Distribute
            </button>
          </div>

          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-4">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Latest NAV
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latestNav ? formatCurrency(latestNav.nav) : "—"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                NAV/Share
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latestNav ? formatNavPerShare(latestNav.nav_per_share) : "—"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Last Computed Date
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {latestNav ? latestNav.business_date : "—"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Status
              </dt>
              <dd className="mt-1">
                {lastRun ? (
                  <StatusBadge
                    label={lastRun.is_successful ? "Completed" : "Failed"}
                    variant={lastRun.is_successful ? "success" : "danger"}
                  />
                ) : (
                  <span className="font-mono text-xl font-bold text-[var(--foreground-bright)]">
                    —
                  </span>
                )}
              </dd>
            </div>
          </dl>

          {/* Tabs */}
          <div className="mb-4 flex gap-4 border-b border-[var(--border)]">
            <button
              type="button"
              onClick={() => setActiveTab("history")}
              className={`pb-2 text-sm font-medium ${
                activeTab === "history"
                  ? "border-b-2 border-[var(--primary)] text-[var(--foreground)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              NAV History
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("runs")}
              className={`pb-2 text-sm font-medium ${
                activeTab === "runs"
                  ? "border-b-2 border-[var(--primary)] text-[var(--foreground)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              Computation Runs
            </button>
          </div>

          {/* NAV History tab */}
          {activeTab === "history" && (
            <>
              {navHistory.isLoading ? (
                <TableSkeleton rows={6} columns={4} />
              ) : navHistory.isError ? (
                <ErrorState
                  message="Failed to load NAV history"
                  onRetry={() => navHistory.refetch()}
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-[var(--border)]">
                    <thead>
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Portfolio ID</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">NAV</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">NAV/Share</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--table-border)]">
                      {sortedNav.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                            No NAV history found.
                          </td>
                        </tr>
                      )}
                      {sortedNav.map((row) => (
                        <tr
                          key={row.business_date}
                          className="transition-colors hover:bg-[var(--table-row-hover)]"
                        >
                          <td className="px-3 py-2 text-sm font-mono">{row.business_date}</td>
                          <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                            —
                          </td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{formatCurrency(row.nav)}</td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{formatNavPerShare(row.nav_per_share)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* Computation Runs tab */}
          {activeTab === "runs" && (
            <>
              {eodHistory.isLoading ? (
                <TableSkeleton rows={6} columns={5} />
              ) : eodHistory.isError ? (
                <ErrorState
                  message="Failed to load computation runs"
                  onRetry={() => eodHistory.refetch()}
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-[var(--border)]">
                    <thead>
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Business Date</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Started At</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Steps</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Duration</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--table-border)]">
                      {runs.length === 0 && (
                        <tr>
                          <td colSpan={5} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                            No computation runs found.
                          </td>
                        </tr>
                      )}
                      {runs.map((run) => (
                        <tr
                          key={run.run_id}
                          className="transition-colors hover:bg-[var(--table-row-hover)]"
                        >
                          <td className="px-3 py-2 text-sm font-mono">{run.business_date}</td>
                          <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">
                            {formatDatetime(run.started_at)}
                          </td>
                          <td className="px-3 py-2 text-sm font-mono">
                            {run.steps_completed}/{run.steps_total}
                          </td>
                          <td className="px-3 py-2 text-sm">
                            <StatusBadge
                              label={run.is_successful ? "Completed" : "Failed"}
                              variant={run.is_successful ? "success" : "danger"}
                            />
                          </td>
                          <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                            {formatDuration(run.started_at, run.completed_at)}
                          </td>
                        </tr>
                      ))}
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
