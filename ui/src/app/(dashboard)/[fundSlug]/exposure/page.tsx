"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ExposureBreakdowns } from "@/features/exposure/components/exposure-breakdowns";
import { ExposureSummary } from "@/features/exposure/components/exposure-summary";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export default function ExposurePage() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Exposure</h1>
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
          <ExposureSummary portfolioId={activePortfolioId} />
          <ExposureBreakdowns portfolioId={activePortfolioId} />
        </>
      )}
    </div>
  );
}
