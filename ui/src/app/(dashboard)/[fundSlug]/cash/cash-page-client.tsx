"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CashDashboard } from "@/features/cash/components/cash-dashboard";
import { CashProjection } from "@/features/cash/components/cash-projection";
import { SettlementLadder } from "@/features/cash/components/settlement-ladder";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function CashPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Cash Management</h1>
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
            <h2 className="mb-3 text-lg font-semibold">Balances</h2>
            <CashDashboard portfolioId={activePortfolioId} />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Settlement Ladder</h2>
            <SettlementLadder portfolioId={activePortfolioId} />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">Cash Projection</h2>
            <CashProjection portfolioId={activePortfolioId} />
          </section>
        </>
      )}
    </div>
  );
}
