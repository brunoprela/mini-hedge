"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CardSkeleton } from "@mini-hedge/ui";
import { AttributionDashboard } from "@/features/attribution/components/attribution-dashboard";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function AttributionPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Attribution</h1>
        {portfolios && (
          <PortfolioSelector
            portfolios={portfolios}
            value={activePortfolioId}
            onChange={setSelectedPortfolioId}
          />
        )}
      </div>

      {isLoading && <CardSkeleton count={3} />}

      {activePortfolioId && (
        <SectionPanel title="Performance Attribution">
          <div className="p-3">
            <AttributionDashboard portfolioId={activePortfolioId} />
          </div>
        </SectionPanel>
      )}
    </div>
  );
}
