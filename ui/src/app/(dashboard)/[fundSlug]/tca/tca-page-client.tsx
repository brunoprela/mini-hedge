"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { TCADashboard } from "@/features/tca/components/tca-dashboard";
import { FundTCASummaryCard } from "@/features/tca/components/fund-tca-summary";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function TCAPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Transaction Cost Analysis</h1>
        {portfolios && portfolios.length > 1 && (
          <select
            value={activePortfolioId}
            onChange={(e) => setSelectedPortfolioId(e.target.value)}
            className="rounded-md border border-(--border) bg-transparent px-3 py-1.5 text-sm"
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        )}
      </div>
      {isLoading && <p className="text-sm text-(--muted-foreground)">Loading...</p>}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Fund Summary</h2>
        <FundTCASummaryCard />
      </section>
      {activePortfolioId && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Portfolio Detail</h2>
          <TCADashboard portfolioId={activePortfolioId} />
        </section>
      )}
    </div>
  );
}
