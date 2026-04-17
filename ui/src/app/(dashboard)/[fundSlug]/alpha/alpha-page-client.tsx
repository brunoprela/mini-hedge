"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CardSkeleton } from "@mini-hedge/ui";
import { orderIntentsQueryOptions } from "@/features/alpha/api";
import { OptimizationPanel } from "@/features/alpha/components/optimization-panel";
import { OrderIntentGantt } from "@/features/alpha/components/order-intent-gantt";
import { OrderIntentsTable } from "@/features/alpha/components/order-intents-table";
import { WhatIfForm } from "@/features/alpha/components/what-if-form";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { CollapsibleSection } from "@/shared/components/collapsible-section";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type AlphaTab = "what-if" | "optimization" | "intents";

const TABS: { id: AlphaTab; label: string }[] = [
  { id: "what-if", label: "What-If Scenario" },
  { id: "optimization", label: "Optimization" },
  { id: "intents", label: "Order Intents" },
];

export function AlphaPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<AlphaTab>("what-if");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  const { data: intents } = useQuery({
    ...orderIntentsQueryOptions(fundSlug, activePortfolioId),
    enabled: !!activePortfolioId,
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Alpha Engine</h1>
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
        <SectionPanel
          title="Alpha Tools"
          tabs={TABS.map((tab) => (
            <ToolbarTab
              key={tab.id}
              label={tab.label}
              active={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
            />
          ))}
        >
          <div className="p-3">
            {activeTab === "what-if" && <WhatIfForm portfolioId={activePortfolioId} />}
            {activeTab === "optimization" && <OptimizationPanel portfolioId={activePortfolioId} />}
            {activeTab === "intents" && <OrderIntentsTable portfolioId={activePortfolioId} />}
          </div>
        </SectionPanel>
      )}

      {activePortfolioId && intents && intents.length > 0 && (
        <CollapsibleSection title="Execution Timeline" defaultOpen={false}>
          <OrderIntentGantt intents={intents} />
        </CollapsibleSection>
      )}
    </div>
  );
}
