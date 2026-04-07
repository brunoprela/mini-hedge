"use client";

import { useQuery } from "@tanstack/react-query";
import { Receipt } from "lucide-react";
import { useState } from "react";
import { AccrualsTable, FeeScheduleCard } from "@/features/fees";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function FeesPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Receipt className="h-6 w-6 text-[var(--primary)]" />
          <h1 className="text-2xl font-semibold">Fees</h1>
        </div>
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

      <FeeScheduleCard />

      {activePortfolioId && (
        <div>
          <h2 className="mb-3 text-lg font-medium">Daily Accruals</h2>
          <AccrualsTable portfolioId={activePortfolioId} />
        </div>
      )}
    </div>
  );
}
