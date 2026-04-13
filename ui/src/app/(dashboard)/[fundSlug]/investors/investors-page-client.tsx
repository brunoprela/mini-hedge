"use client";

import { useState } from "react";
import { CapitalOverviewCards } from "@/features/investors/components/capital-overview-cards";
import { CreateInvestorDialog } from "@/features/investors/components/create-investor-dialog";
import { InvestorTable } from "@/features/investors/components/investor-table";
import { NavAllocationChart } from "@/features/investors/components/nav-allocation-chart";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";

export function InvestorsPageClient() {
  const [showCreate, setShowCreate] = useState(false);
  const { can } = usePermission();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Investors</h1>
        {can(Permission.CAPITAL_WRITE) && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
          >
            + Add Investor
          </button>
        )}
      </div>
      <CapitalOverviewCards />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_280px]">
        <InvestorTable />
        <NavAllocationChart />
      </div>
      {showCreate && <CreateInvestorDialog onClose={() => setShowCreate(false)} />}
    </div>
  );
}
