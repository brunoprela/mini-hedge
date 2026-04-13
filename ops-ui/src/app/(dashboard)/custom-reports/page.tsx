"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { ErrorState } from "@/shared/components/error-state";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
import type { InvestorInfo } from "@/shared/types";

interface FilingRecord {
  id: string;
  filing_type: string;
  fund_slug: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  status: string;
}

type ReportType = "form-pf" | "13f" | "investor-statement" | "performance-letter";

const REPORT_OPTIONS: { value: ReportType; label: string }[] = [
  { value: "form-pf", label: "Form PF" },
  { value: "13f", label: "13F Filing" },
  { value: "investor-statement", label: "Investor Statement" },
  { value: "performance-letter", label: "Performance Letter" },
];

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  completed: "success",
  pending: "warning",
  failed: "danger",
  draft: "neutral",
};

export default function CustomReportsPage() {
  const queryClient = useQueryClient();

  const [fundSlug, setFundSlug] = useState("");
  const [_portfolioId, setPortfolioId] = useState("");

  const [reportType, setReportType] = useState<ReportType>("form-pf");
  const [asOfDate, setAsOfDate] = useState("");
  const [investorId, setInvestorId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");

  // Fetch filings history
  const {
    data: filingsData,
    isLoading: filingsLoading,
    isError: filingsError,
  } = useQuery({
    queryKey: ["regulatory", "filings"],
    queryFn: () => apiFetch<{ items: FilingRecord[] }>("regulatory/filings?limit=50"),
  });

  // Fetch investors for the selected fund
  const { data: investors } = useQuery({
    queryKey: ["investors", fundSlug],
    queryFn: () => apiFetch<InvestorInfo[]>(`funds/${fundSlug}/capital/investors`),
    enabled: !!fundSlug && reportType === "investor-statement",
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["regulatory", "filings"] });

  const generateFormPF = useMutation({
    mutationFn: () =>
      apiFetch("regulatory/form-pf", {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug, as_of_date: asOfDate }),
      }),
    onSuccess: () => { invalidate(); toast.success("Form PF report generated"); },
    onError: (err) => toast.error(err.message),
  });

  const generate13F = useMutation({
    mutationFn: () =>
      apiFetch("regulatory/13f", {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug, as_of_date: asOfDate }),
      }),
    onSuccess: () => { invalidate(); toast.success("13F Filing report generated"); },
    onError: (err) => toast.error(err.message),
  });

  const generateStatement = useMutation({
    mutationFn: () =>
      apiFetch("regulatory/investor-statement", {
        method: "POST",
        body: JSON.stringify({
          fund_slug: fundSlug,
          investor_id: investorId,
          period_start: periodStart,
          period_end: periodEnd,
        }),
      }),
    onSuccess: () => { invalidate(); toast.success("Investor Statement generated"); },
    onError: (err) => toast.error(err.message),
  });

  const generateLetter = useMutation({
    mutationFn: () =>
      apiFetch("regulatory/performance-letter", {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug, period_end: periodEnd }),
      }),
    onSuccess: () => { invalidate(); toast.success("Performance Letter generated"); },
    onError: (err) => toast.error(err.message),
  });

  const anyPending =
    generateFormPF.isPending ||
    generate13F.isPending ||
    generateStatement.isPending ||
    generateLetter.isPending;

  const filings = filingsData?.items ?? [];

  const completedCount = filings.filter((f) => f.status === "completed").length;
  const pendingCount = filings.filter((f) => f.status === "pending").length;
  const failedCount = filings.filter((f) => f.status === "failed").length;

  function isGenerateDisabled(): boolean {
    if (!fundSlug || anyPending) return true;
    switch (reportType) {
      case "form-pf":
      case "13f":
        return !asOfDate;
      case "investor-statement":
        return !investorId || !periodStart || !periodEnd;
      case "performance-letter":
        return !periodEnd;
    }
  }

  function handleGenerate() {
    switch (reportType) {
      case "form-pf":
        generateFormPF.mutate();
        break;
      case "13f":
        generate13F.mutate();
        break;
      case "investor-statement":
        generateStatement.mutate();
        break;
      case "performance-letter":
        generateLetter.mutate();
        break;
    }
  }

  const fieldClass =
    "w-full rounded border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm text-[var(--foreground)]";

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-[var(--foreground)]">Custom Reports</h1>

      <FundPortfolioPicker
        fundSlug={fundSlug}
        onFundChange={setFundSlug}
        portfolioId={_portfolioId}
        onPortfolioChange={setPortfolioId}
        showPortfolio={false}
      />

      {/* KPI Strip */}
      <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-3">
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Completed</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{completedCount}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Pending</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{pendingCount}</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Failed</dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{failedCount}</dd>
        </div>
      </dl>

      {/* Report Builder Card */}
      <div className="mb-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">Build Report</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <label className="block">
            <span className="block text-xs text-[var(--muted-foreground)] mb-1">Report Type</span>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value as ReportType)}
              className={fieldClass}
            >
              {REPORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </label>

          {/* Dynamic fields based on report type */}
          {(reportType === "form-pf" || reportType === "13f") && (
            <label className="block">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">As-of Date</span>
              <input
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                className={fieldClass}
              />
            </label>
          )}

          {reportType === "investor-statement" && (
            <>
              <label className="block">
                <span className="block text-xs text-[var(--muted-foreground)] mb-1">Investor</span>
                <select
                  value={investorId}
                  onChange={(e) => setInvestorId(e.target.value)}
                  className={fieldClass}
                  disabled={!fundSlug}
                >
                  <option value="">Select investor...</option>
                  {(investors ?? []).map((inv) => (
                    <option key={inv.id} value={inv.id}>{inv.name}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="block text-xs text-[var(--muted-foreground)] mb-1">Period Start</span>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className={fieldClass}
                />
              </label>
              <label className="block">
                <span className="block text-xs text-[var(--muted-foreground)] mb-1">Period End</span>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className={fieldClass}
                />
              </label>
            </>
          )}

          {reportType === "performance-letter" && (
            <label className="block">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">Period End</span>
              <input
                type="date"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                className={fieldClass}
              />
            </label>
          )}
        </div>
        <div className="mt-4">
          <button
            onClick={handleGenerate}
            disabled={isGenerateDisabled()}
            className="inline-flex items-center gap-2 rounded bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {anyPending && <Loader2 size={14} className="animate-spin" />}
            Generate Report
          </button>
        </div>
      </div>

      {/* Report History Table */}
      {filingsError ? (
        <ErrorState message="Failed to load report history" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="min-w-full divide-y divide-[var(--border)]">
            <thead className="bg-[var(--card)]">
              <tr>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Type</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fund</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Period</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Generated At</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {filingsLoading && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">Loading...</td>
                </tr>
              )}
              {!filingsLoading && filings.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">No reports generated yet</td>
                </tr>
              )}
              {filings.map((f) => (
                <tr key={f.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                  <td className="px-3 py-2 text-sm font-medium text-[var(--foreground)]">{f.filing_type}</td>
                  <td className="px-3 py-2 text-sm text-[var(--foreground)]">{f.fund_slug}</td>
                  <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]">
                    {f.period_start} &mdash; {f.period_end}
                  </td>
                  <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                    {new Date(f.generated_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge label={f.status} variant={STATUS_VARIANT[f.status] ?? "neutral"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
