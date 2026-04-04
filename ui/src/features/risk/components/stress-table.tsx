"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
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

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading stress tests...</div>;
  }

  if (!results || results.length === 0) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">No stress test results available.</p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
            <th className="px-4 py-2 text-left font-medium text-[var(--muted-foreground)]">
              Scenario
            </th>
            <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
              PnL Impact
            </th>
            <th className="px-4 py-2 text-right font-medium text-[var(--muted-foreground)]">
              % Change
            </th>
            <th className="w-10 px-4 py-2" />
          </tr>
        </thead>
        <tbody>
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
        className="border-b border-[var(--table-border)] last:border-0 cursor-pointer hover:bg-[var(--table-row-hover)]"
        onClick={() => hasImpacts && setExpanded(!expanded)}
      >
        <td className="px-4 py-2 font-medium">{result.scenario_name}</td>
        <td
          className={`px-4 py-2 text-right font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}
        >
          {fmtCurrency(result.total_pnl_impact)}
        </td>
        <td
          className={`px-4 py-2 text-right font-mono ${pnl < 0 ? "text-[var(--destructive)]" : ""}`}
        >
          {fmtPct(result.total_pct_change)}
        </td>
        <td className="px-4 py-2 text-center text-[var(--muted-foreground)]">
          {hasImpacts ? (expanded ? "▾" : "▸") : ""}
        </td>
      </tr>
      {expanded &&
        result.position_impacts.map((impact) => {
          const impactPnl = parseFloat(impact.pnl_impact);
          return (
            <tr
              key={impact.instrument_id}
              className="border-b border-[var(--table-border)] last:border-0 bg-[var(--muted)]"
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
            </tr>
          );
        })}
    </>
  );
}
