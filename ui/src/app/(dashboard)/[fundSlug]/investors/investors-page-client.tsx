"use client";

import { CapitalOverviewCards } from "@/features/investors/components/capital-overview-cards";
import { InvestorTable } from "@/features/investors/components/investor-table";

export function InvestorsPageClient() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Investors</h1>
      <CapitalOverviewCards />
      <InvestorTable />
    </div>
  );
}
