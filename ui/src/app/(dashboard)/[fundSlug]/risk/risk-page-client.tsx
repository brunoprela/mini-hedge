"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { FactorBreakdown } from "@/features/risk/components/factor-breakdown";
import { RiskDashboard } from "@/features/risk/components/risk-dashboard";
import { StressTable } from "@/features/risk/components/stress-table";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function RiskPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Risk</h1>
        {portfolios && portfolios.length > 1 && (
          <select
            value={activePortfolioId}
            onChange={(e) => setSelectedPortfolioId(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {isLoading && <p className="text-sm text-[var(--muted-foreground)]">Loading portfolios...</p>}

      {activePortfolioId && (
        <>
          <section>
            <h2 className="mb-3 text-lg font-semibold">Snapshot</h2>
            <RiskDashboard portfolioId={activePortfolioId} />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Stress Tests</h2>
            <StressTable portfolioId={activePortfolioId} />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Factor Decomposition</h2>
            <FactorBreakdown portfolioId={activePortfolioId} />
          </section>
        </>
      )}
    </div>
  );
}
