"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { apiFetch } from "@/shared/lib/api";

export default function DataQualityPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");

  const { data: instruments } = useQuery({
    queryKey: ["instruments", "count"],
    queryFn: () => apiFetch<{ items: unknown[]; total: number }>("instruments?limit=1"),
  });

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Data Quality</h2>

      <div className="mb-6">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
          showPortfolio={false}
        />
      </div>

      <p className="mb-6 text-sm text-[var(--muted-foreground)]">
        Data quality monitoring is under development. Instrument coverage and
        price freshness dashboards coming soon.
      </p>

      <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-1 max-w-xs">
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Total Instruments
          </dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
            {instruments?.total ?? "--"}
          </dd>
        </div>
      </dl>
    </div>
  );
}
