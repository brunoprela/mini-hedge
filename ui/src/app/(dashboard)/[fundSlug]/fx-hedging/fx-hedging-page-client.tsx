"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { useState } from "react";
import {
  ForwardsTable,
  FXSummaryCards,
  HedgeRecommendations,
  InterestRatesPanel,
} from "@/features/fx-hedging";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type Tab = "forwards" | "recommendations" | "rates";

export function FXHedgingPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<Tab>("forwards");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  const tabs: { key: Tab; label: string }[] = [
    { key: "forwards", label: "Forwards" },
    { key: "recommendations", label: "Hedge Recommendations" },
    { key: "rates", label: "Interest Rates" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ArrowLeftRight className="h-6 w-6 text-[var(--primary)]" />
          <h1 className="text-2xl font-semibold">FX Hedging</h1>
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

      {activePortfolioId && (
        <>
          <FXSummaryCards portfolioId={activePortfolioId} />

          <div className="flex gap-1 border-b border-[var(--border)]">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "forwards" && <ForwardsTable portfolioId={activePortfolioId} />}
          {activeTab === "recommendations" && (
            <HedgeRecommendations portfolioId={activePortfolioId} />
          )}
          {activeTab === "rates" && <InterestRatesPanel />}
        </>
      )}
    </div>
  );
}
