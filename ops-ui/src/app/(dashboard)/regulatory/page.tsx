"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";

interface FilingRecord {
  id: string;
  filing_type: string;
  fund_slug: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  status: string;
}

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  completed: "success",
  pending: "warning",
  failed: "danger",
  draft: "neutral",
};

export default function RegulatoryPage() {
  const queryClient = useQueryClient();

  const [fundSlug, setFundSlug] = useState("");
  const [_portfolioId, setPortfolioId] = useState("");
  const [asOfDate, setAsOfDate] = useState("");
  const [investorId, setInvestorId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);

  const { data, isLoading } = useQuery({
    queryKey: ["regulatory", "filings"],
    queryFn: () => apiFetch<{ items: FilingRecord[] }>("regulatory/filings?limit=50"),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["regulatory", "filings"] });

  const generateFormPF = useMutation({
    mutationFn: () =>
      apiFetch("regulatory/form-pf", {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug, as_of_date: asOfDate }),
      }),
    onSuccess: () => { invalidate(); toast.success("Form PF generated"); },
    onError: (err) => toast.error(err.message),
  });

  const generate13F = useMutation({
    mutationFn: () =>
      apiFetch("regulatory/13f", {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug, as_of_date: asOfDate }),
      }),
    onSuccess: () => { invalidate(); toast.success("13F generated"); },
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
    onSuccess: () => { invalidate(); toast.success("Investor statement generated"); },
    onError: (err) => toast.error(err.message),
  });

  const generateLetter = useMutation({
    mutationFn: () =>
      apiFetch("regulatory/performance-letter", {
        method: "POST",
        body: JSON.stringify({ fund_slug: fundSlug, year, month }),
      }),
    onSuccess: () => { invalidate(); toast.success("Performance letter generated"); },
    onError: (err) => toast.error(err.message),
  });

  const filings = data?.items ?? [];
  const anyPending =
    generateFormPF.isPending ||
    generate13F.isPending ||
    generateStatement.isPending ||
    generateLetter.isPending;

  const inputClass =
    "w-full rounded border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm text-[var(--foreground)]";
  const btnClass =
    "rounded bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50";

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-[var(--foreground)]">Regulatory Reporting</h1>

      <FundPortfolioPicker
        fundSlug={fundSlug}
        onFundChange={setFundSlug}
        portfolioId={_portfolioId}
        onPortfolioChange={setPortfolioId}
        showPortfolio={false}
      />

      {!fundSlug ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund to manage regulatory filings.
        </p>
      ) : (
        <>
          {/* Generate section */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
            <h2 className="text-sm font-medium text-[var(--foreground)]">Generate Filing</h2>

            {/* Row 1: as_of_date + Form PF + 13F */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-44">
                <label className="block text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
                  As-of Date
                </label>
                <input
                  type="date"
                  value={asOfDate}
                  onChange={(e) => setAsOfDate(e.target.value)}
                  className={inputClass}
                />
              </div>
              <button
                onClick={() => generateFormPF.mutate()}
                disabled={!asOfDate || anyPending}
                className={btnClass}
              >
                Generate Form PF
              </button>
              <button
                onClick={() => generate13F.mutate()}
                disabled={!asOfDate || anyPending}
                className={btnClass}
              >
                Generate 13F
              </button>
            </div>

            {/* Row 2: investor_id + period_start + period_end + Statement */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-44">
                <label className="block text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
                  Investor ID
                </label>
                <input
                  type="text"
                  value={investorId}
                  onChange={(e) => setInvestorId(e.target.value)}
                  placeholder="Investor ID for statements"
                  className={inputClass}
                />
              </div>
              <div className="w-40">
                <label className="block text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
                  Period Start
                </label>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="w-40">
                <label className="block text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
                  Period End
                </label>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className={inputClass}
                />
              </div>
              <button
                onClick={() => generateStatement.mutate()}
                disabled={!investorId || !periodStart || !periodEnd || anyPending}
                className={btnClass}
              >
                Generate Statement
              </button>
            </div>

            {/* Row 3: year + month + Letter */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-24">
                <label className="block text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
                  Year
                </label>
                <input
                  type="number"
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                  className={inputClass}
                />
              </div>
              <div className="w-20">
                <label className="block text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
                  Month
                </label>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={month}
                  onChange={(e) => setMonth(Number(e.target.value))}
                  className={inputClass}
                />
              </div>
              <button
                onClick={() => generateLetter.mutate()}
                disabled={anyPending}
                className={btnClass}
              >
                Generate Letter
              </button>
            </div>
          </div>

          {/* Filing history */}
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
                {isLoading && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">Loading...</td>
                  </tr>
                )}
                {!isLoading && filings.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">No filings found</td>
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
        </>
      )}
    </div>
  );
}
