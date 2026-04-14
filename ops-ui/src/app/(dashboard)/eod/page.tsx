"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Play } from "lucide-react";
import { ErrorState } from "@/shared/components/error-state";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
import type { EODRunSummary } from "@/shared/types";

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

export default function EODControlCenterPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [businessDate, setBusinessDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );

  const history = useQuery({
    queryKey: ["eod", "history", fundSlug],
    queryFn: () =>
      apiFetch<EODRunSummary[]>(
        `eod/history?fund_slug=${encodeURIComponent(fundSlug)}&limit=20`,
      ),
    enabled: !!fundSlug,
  });

  const runEod = useMutation({
    mutationFn: (data: { fund_slug: string; business_date: string }) =>
      apiFetch("eod/run", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      toast.success("EOD run triggered");
      queryClient.invalidateQueries({ queryKey: ["eod"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const items = history.data ?? [];
  const lastRun = items.length > 0 ? items[0] : null;

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">EOD Control Center</h2>

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
          Select a fund to view EOD history.
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
              disabled={runEod.isPending || !businessDate}
              onClick={() =>
                runEod.mutate({
                  fund_slug: fundSlug,
                  business_date: businessDate,
                })
              }
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              <Play size={14} />
              {runEod.isPending ? "Running..." : "Run EOD"}
            </button>
          </div>

          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-3">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Last Run Date
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {lastRun ? lastRun.business_date : "—"}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Last Run Status
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
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Steps Completed
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {lastRun
                  ? `${lastRun.steps_completed}/${lastRun.steps_total}`
                  : "—"}
              </dd>
            </div>
          </dl>

          {/* History table */}
          {history.isLoading ? (
            <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
              Loading...
            </p>
          ) : history.isError ? (
            <ErrorState
              message="Failed to load EOD history"
              onRetry={() => history.refetch()}
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
                  {items.length === 0 && (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]"
                      >
                        No EOD runs found.
                      </td>
                    </tr>
                  )}
                  {items.map((run) => (
                    <tr
                      key={run.run_id}
                      className="transition-colors hover:bg-[var(--table-row-hover)]"
                    >
                      <td className="px-3 py-2 text-sm font-mono">
                        {run.business_date}
                      </td>
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
    </div>
  );
}
