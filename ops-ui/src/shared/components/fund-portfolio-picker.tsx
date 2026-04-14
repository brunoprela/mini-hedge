"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api";
import type { FundDetail, Page, PortfolioInfo } from "@/shared/types";

interface FundPortfolioPickerProps {
  fundSlug: string;
  onFundChange: (slug: string) => void;
  portfolioId: string;
  onPortfolioChange: (id: string) => void;
  showPortfolio?: boolean;
}

export function FundPortfolioPicker({
  fundSlug,
  onFundChange,
  portfolioId,
  onPortfolioChange,
  showPortfolio = true,
}: FundPortfolioPickerProps) {
  const { data: fundsPage } = useQuery({
    queryKey: ["admin", "funds", "all"],
    queryFn: () => apiFetch<Page<FundDetail>>("admin/funds?limit=100"),
  });

  const { data: portfolios } = useQuery({
    queryKey: ["portfolios", fundSlug],
    queryFn: () => apiFetch<PortfolioInfo[]>(`portfolios?fund_slug=${fundSlug}`),
    enabled: !!fundSlug && showPortfolio,
  });

  const funds = fundsPage?.items ?? [];

  return (
    <div className="flex items-center gap-3">
      <div>
        <label htmlFor="fund-picker" className="mr-2 text-sm text-[var(--muted-foreground)]">
          Fund
        </label>
        <select
          id="fund-picker"
          value={fundSlug}
          onChange={(e) => {
            onFundChange(e.target.value);
            onPortfolioChange("");
          }}
          className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)]"
        >
          <option value="">Select fund…</option>
          {funds.map((f) => (
            <option key={f.id} value={f.slug}>
              {f.name} ({f.slug})
            </option>
          ))}
        </select>
      </div>

      {showPortfolio && (
        <div>
          <label htmlFor="portfolio-picker" className="mr-2 text-sm text-[var(--muted-foreground)]">
            Portfolio
          </label>
          <select
            id="portfolio-picker"
            value={portfolioId}
            onChange={(e) => onPortfolioChange(e.target.value)}
            disabled={!fundSlug}
            className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm outline-none focus:border-[var(--ring)] disabled:opacity-50"
          >
            <option value="">Select portfolio…</option>
            {portfolios?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.slug})
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
