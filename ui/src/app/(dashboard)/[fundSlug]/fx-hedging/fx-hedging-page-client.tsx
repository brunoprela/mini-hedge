"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
  ForwardsTable,
  FXSummaryCards,
  HedgeRecommendations,
  InterestRatesPanel,
  OpenForwardDialog,
} from "@/features/fx-hedging";
import { triggerMTM } from "@/features/fx-hedging/api";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import type { HedgeRecommendation } from "@/features/fx-hedging/types";

type Tab = "forwards" | "recommendations" | "rates";

interface Prefill {
  base_currency?: string;
  quote_currency?: string;
  direction?: string;
  notional?: string;
  contract_rate?: string;
}

export function FXHedgingPageClient() {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<Tab>("forwards");
  const [showOpenForward, setShowOpenForward] = useState(false);
  const [prefill, setPrefill] = useState<Prefill | undefined>(undefined);

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  const mtmMutation = useMutation({
    mutationFn: () => triggerMTM(fundSlug, activePortfolioId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fx-forwards"] });
      queryClient.invalidateQueries({ queryKey: ["fx-hedging-summary"] });
      toast.success("MTM refresh triggered");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to refresh MTM");
    },
  });

  const tabs: { key: Tab; label: string }[] = [
    { key: "forwards", label: "Forwards" },
    { key: "recommendations", label: "Hedge Recommendations" },
    { key: "rates", label: "Interest Rates" },
  ];

  function handleExecuteRecommendation(rec: HedgeRecommendation) {
    setPrefill({
      base_currency: rec.base_currency,
      quote_currency: rec.quote_currency,
      direction: rec.direction,
      notional: rec.notional,
      contract_rate: rec.estimated_forward,
    });
    setShowOpenForward(true);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">FX Hedging</h1>
        <div className="flex items-center gap-2">
          {activePortfolioId && (
            <>
              <button
                type="button"
                onClick={() => {
                  setPrefill(undefined);
                  setShowOpenForward(true);
                }}
                className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
              >
                + Open Forward
              </button>
              <button
                type="button"
                onClick={() => mtmMutation.mutate()}
                disabled={mtmMutation.isPending}
                className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--muted)] disabled:opacity-50"
              >
                {mtmMutation.isPending ? "Refreshing..." : "Refresh MTM"}
              </button>
            </>
          )}
          {portfolios && (
            <PortfolioSelector
              portfolios={portfolios}
              value={activePortfolioId}
              onChange={setSelectedPortfolioId}
            />
          )}
        </div>
      </div>

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      {activePortfolioId && (
        <>
          <FXSummaryCards portfolioId={activePortfolioId} />

          <div className="flex gap-1 border-b border-[var(--border)]">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
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
            <HedgeRecommendations
              portfolioId={activePortfolioId}
              onExecuteRecommendation={handleExecuteRecommendation}
            />
          )}
          {activeTab === "rates" && <InterestRatesPanel />}
        </>
      )}

      {showOpenForward && activePortfolioId && (
        <OpenForwardDialog
          portfolioId={activePortfolioId}
          onClose={() => setShowOpenForward(false)}
          prefill={prefill}
        />
      )}
    </div>
  );
}
