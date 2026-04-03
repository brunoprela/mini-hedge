"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { RuleTable } from "@/features/compliance/components/rule-table";
import { ViolationsPanel } from "@/features/compliance/components/violations-panel";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export default function CompliancePage() {
  const { fundSlug } = useFundContext();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Compliance</h1>

      {/* Rules section */}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Rules</h2>
        <RuleTable />
      </section>

      {/* Violations section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Active Violations</h2>
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
        {activePortfolioId && <ViolationsPanel portfolioId={activePortfolioId} />}
      </section>
    </div>
  );
}
