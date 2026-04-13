"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { stressTestsQueryOptions } from "../api";
import type { StressTestResult } from "../types";

function fmtCurrency(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmtPct(v: string) {
  return `${parseFloat(v).toFixed(2)}%`;
}

export function StressTable({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: results, isLoading } = useQuery(stressTestsQueryOptions(fundSlug, portfolioId));
  const exportCSV = useExportCSV();

  const handleExport = () => {
    if (!results || results.length === 0) return;
    const exportData = results.map((r) => ({
      scenario: r.scenario_name,
      type: r.scenario_type,
      pnl_impact: r.total_pnl_impact,
      pct_change: r.total_pct_change,
      calculated_at: r.calculated_at,
    }));
    exportCSV(exportData as unknown as Record<string, unknown>[], `stress-tests-${portfolioId}`);
  };

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading stress tests...</div>;
  }

  if (!results || results.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleExport}
          title="Export to CSV"
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
        >
          <Download className="h-4 w-4" />
          CSV
        </button>
      </div>
      <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
        <table className="min-w-full divide-y divide-[var(--border)]">
          <thead>
            <tr>
              <th scope="col" className="px-3 py-2 text-left text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                Scenario
              </th>
              <th scope="col" className="px-3 py-2 text-right text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                PnL Impact
              </th>
              <th scope="col" className="px-3 py-2 text-right text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                % Change
              </th>
              <th scope="col" className="px-3 py-2 text-left text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                Actions
              </th>
              <th scope="col" className="w-10 px-3 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {results.map((result) => (
              <StressRow
                key={result.scenario_name}
                result={result}
                fundSlug={fundSlug}
                portfolioId={portfolioId}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StressRow({
  result,
  fundSlug,
  portfolioId,
}: {
  result: StressTestResult;
  fundSlug: string;
  portfolioId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const pnl = parseFloat(result.total_pnl_impact);
  const hasImpacts = result.position_impacts.length > 0;

  return (
    <>
      <tr
        className="cursor-pointer transition-colors hover:bg-[var(--table-row-hover)]"
        onClick={() => hasImpacts && setExpanded(!expanded)}
      >
        <td className="px-3 py-1.5 font-medium">{result.scenario_name}</td>
        <td
          className={`px-3 py-1.5 text-right font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}
        >
          {fmtCurrency(result.total_pnl_impact)}
        </td>
        <td
          className={`px-3 py-1.5 text-right font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}
        >
          {fmtPct(result.total_pct_change)}
        </td>
        <td className="px-3 py-1.5">
          {pnl < -10000 && (
            <div className="flex gap-2">
              <Link
                href={`/${fundSlug}/alpha?portfolio=${portfolioId}&scenario=${encodeURIComponent(result.scenario_name)}&loss=${Math.abs(pnl).toFixed(0)}`}
                className="text-xs text-[var(--primary)] hover:underline"
              >
                What-If →
              </Link>
              <Link
                href={`/${fundSlug}/fx-hedging?hedge_scenario=${encodeURIComponent(result.scenario_name)}&loss=${Math.abs(pnl).toFixed(0)}`}
                className="text-xs text-[var(--primary)] hover:underline"
              >
                Hedge →
              </Link>
            </div>
          )}
        </td>
        <td className="px-3 py-1.5 text-center text-[var(--muted-foreground)]">
          {hasImpacts ? (expanded ? "▾" : "▸") : ""}
        </td>
      </tr>
      {expanded &&
        result.position_impacts.map((impact) => {
          const impactPnl = parseFloat(impact.pnl_impact);
          return (
            <tr
              key={impact.instrument_id}
              className="bg-[var(--muted)]"
            >
              <td className="px-4 py-1.5 pl-8 text-xs text-[var(--muted-foreground)]">
                <Link
                  href={`/${fundSlug}/portfolio/${portfolioId}#positions`}
                  className="text-[var(--foreground)] underline-offset-2 hover:underline"
                >
                  {impact.instrument_id}
                </Link>
              </td>
              <td
                className={`px-4 py-1.5 text-right font-mono text-xs ${impactPnl < 0 ? "text-[var(--destructive)]" : ""}`}
              >
                {fmtCurrency(impact.pnl_impact)}
              </td>
              <td
                className={`px-4 py-1.5 text-right font-mono text-xs ${impactPnl < 0 ? "text-[var(--destructive)]" : ""}`}
              >
                {fmtPct(impact.pct_change)}
              </td>
              <td />
              <td />
            </tr>
          );
        })}
    </>
  );
}
