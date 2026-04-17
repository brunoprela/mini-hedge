"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState, TableSkeleton } from "@mini-hedge/ui";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@mini-hedge/ui";
import { api, fundHeaders } from "@/shared/lib/api-client";

type Tab = "schedules" | "accruals";

function fmtUSD(value: string): string {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return value;
  return num.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
}

export default function FeesPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [businessDate, setBusinessDate] = useState(new Date().toISOString().slice(0, 10));
  const [activeTab, setActiveTab] = useState<Tab>("schedules");

  const summaryQuery = useQuery({
    queryKey: ["fees", "summary", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/funds/{fund_slug}/fees/summary",
        {
          params: { path: { fund_slug: fundSlug }, query: {} },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!fundSlug,
  });

  const accrualsQuery = useQuery({
    queryKey: ["fees", "accruals", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/funds/{fund_slug}/fees/accruals",
        {
          params: { path: { fund_slug: fundSlug }, query: {} },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!fundSlug && activeTab === "accruals",
  });

  const schedulesQuery = useQuery({
    queryKey: ["fees", "schedules", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/funds/{fund_slug}/fees/schedules",
        {
          params: { path: { fund_slug: fundSlug } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!fundSlug && activeTab === "schedules",
  });

  const accrueDaily = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST(
        "/api/v1/funds/{fund_slug}/fees/accrue-daily",
        {
          params: { path: { fund_slug: fundSlug } },
          body: { business_date: businessDate, share_class: "default" },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fees"] });
      toast.success("Daily accrual completed");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const crystallize = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST(
        "/api/v1/funds/{fund_slug}/fees/crystallize",
        {
          params: { path: { fund_slug: fundSlug } },
          body: { business_date: businessDate, share_class: "default" },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fees"] });
      toast.success("Crystallization completed");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const totals = summaryQuery.data?.totals;

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Fee Management</h2>

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
          Select a fund to view fee data.
        </p>
      ) : (
        <>
          {/* KPI strip */}
          {summaryQuery.isError ? (
            <ErrorState message={summaryQuery.error.message} onRetry={() => summaryQuery.refetch()} />
          ) : (
            <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-4">
              <div className="bg-[var(--card)] px-4 py-4">
                <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Mgmt Fees</dt>
                <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                  {totals?.management ? fmtUSD(totals.management) : "—"}
                </dd>
              </div>
              <div className="bg-[var(--card)] px-4 py-4">
                <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Perf Fees</dt>
                <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                  {totals?.performance ? fmtUSD(totals.performance) : "—"}
                </dd>
              </div>
              <div className="bg-[var(--card)] px-4 py-4">
                <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Admin Fees</dt>
                <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                  {totals?.admin ? fmtUSD(totals.admin) : "—"}
                </dd>
              </div>
              <div className="bg-[var(--card)] px-4 py-4">
                <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Total</dt>
                <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                  {totals ? fmtUSD(Object.values(totals).reduce((s, v) => s + parseFloat(v || "0"), 0).toString()) : "—"}
                </dd>
              </div>
            </dl>
          )}

          {/* Actions */}
          <div className="mb-6 flex flex-wrap items-end gap-3">
            <label className="block">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">Business Date</span>
              <input
                type="date"
                value={businessDate}
                onChange={(e) => setBusinessDate(e.target.value)}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              />
            </label>
            <button
              type="button"
              disabled={accrueDaily.isPending}
              onClick={() => accrueDaily.mutate()}
              className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {accrueDaily.isPending && <Loader2 size={14} className="animate-spin" />}
              Accrue Daily
            </button>
            <button
              type="button"
              disabled={crystallize.isPending}
              onClick={() => crystallize.mutate()}
              className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {crystallize.isPending && <Loader2 size={14} className="animate-spin" />}
              Crystallize
            </button>
          </div>

          {/* Tabs */}
          <div className="mb-4 flex gap-4 border-b border-[var(--border)]">
            {(["schedules", "accruals"] as const).map((tab) => (
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

          {/* Schedules */}
          {activeTab === "schedules" && (
            <>
              {schedulesQuery.isLoading ? (
                <TableSkeleton rows={5} columns={7} />
              ) : schedulesQuery.isError ? (
                <ErrorState message={schedulesQuery.error.message} onRetry={() => schedulesQuery.refetch()} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-[var(--border)]">
                    <thead>
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Share Class</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Mgmt Fee (bps)</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Perf Fee (%)</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Hurdle (%)</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">HWM</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Crystal. Freq</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Payment Freq</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--table-border)]">
                      {schedulesQuery.data?.map((row) => (
                        <tr key={row.share_class} className="transition-colors hover:bg-[var(--table-row-hover)]">
                          <td className="px-3 py-2 text-sm font-medium">{row.share_class}</td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{row.management_fee_bps}</td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{row.performance_fee_pct}</td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{row.hurdle_rate_pct}</td>
                          <td className="px-3 py-2 text-sm">
                            {row.high_water_mark ? (
                              <StatusBadge label="Yes" variant="success" />
                            ) : (
                              <StatusBadge label="No" variant="neutral" />
                            )}
                          </td>
                          <td className="px-3 py-2 text-sm">{row.crystallization_frequency}</td>
                          <td className="px-3 py-2 text-sm">{row.payment_frequency}</td>
                        </tr>
                      ))}
                      {schedulesQuery.data?.length === 0 && (
                        <tr>
                          <td colSpan={7} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">No fee schedules found.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* Accruals */}
          {activeTab === "accruals" && (
            <>
              {accrualsQuery.isLoading ? (
                <TableSkeleton rows={5} columns={6} />
              ) : accrualsQuery.isError ? (
                <ErrorState message={accrualsQuery.error.message} onRetry={() => accrualsQuery.refetch()} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-[var(--border)]">
                    <thead>
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fee Type</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Accrued</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Cumulative</th>
                        <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                        <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">NAV Basis</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--table-border)]">
                      {accrualsQuery.data?.map((row) => (
                        <tr key={`${row.accrual_date}-${row.fee_type}`} className="transition-colors hover:bg-[var(--table-row-hover)]">
                          <td className="px-3 py-2 text-sm">{row.accrual_date}</td>
                          <td className="px-3 py-2 text-sm">{row.fee_type}</td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{fmtUSD(row.accrued_amount)}</td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{fmtUSD(row.cumulative_amount)}</td>
                          <td className="px-3 py-2 text-sm">
                            <StatusBadge
                              label={row.status}
                              variant={row.status === "crystallized" ? "success" : row.status === "accrued" ? "warning" : "neutral"}
                            />
                          </td>
                          <td className="px-3 py-2 text-sm text-right font-mono">{fmtUSD(row.nav_basis)}</td>
                        </tr>
                      ))}
                      {accrualsQuery.data?.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">No accruals found.</td>
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
