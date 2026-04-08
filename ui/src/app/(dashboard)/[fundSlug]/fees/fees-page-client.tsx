"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AccrualsTable, FeeScheduleCard } from "@/features/fees";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type FeeTab = "schedule" | "accruals";

const TABS: { id: FeeTab; label: string }[] = [
  { id: "schedule", label: "Fee Schedule" },
  { id: "accruals", label: "Daily Accruals" },
];

export function FeesPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<FeeTab>("schedule");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Fees</h1>
        {portfolios && (
          <PortfolioSelector
            portfolios={portfolios}
            value={activePortfolioId}
            onChange={setSelectedPortfolioId}
          />
        )}
      </div>

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      <SectionPanel
        title="Fee Management"
        tabs={
          <>
            {TABS.map((tab) => (
              <ToolbarTab
                key={tab.id}
                label={tab.label}
                active={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
              />
            ))}
          </>
        }
      >
        <div className="p-3">
          {activeTab === "schedule" && <FeeScheduleCard />}
          {activeTab === "accruals" && activePortfolioId && (
            <AccrualsTable portfolioId={activePortfolioId} />
          )}
        </div>
      </SectionPanel>
    </div>
  );
}
