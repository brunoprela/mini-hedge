"use client";

import { useState } from "react";
import { CapitalOverviewCards } from "@/features/investors/components/capital-overview-cards";
import { CreateInvestorDialog } from "@/features/investors/components/create-investor-dialog";
import { InvestorTable } from "@/features/investors/components/investor-table";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";

export function InvestorsPageClient() {
  const [showCreate, setShowCreate] = useState(false);
  const { can } = usePermission();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Investors</h1>
        {can(Permission.CAPITAL_WRITE) && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white"
          >
            + Add Investor
          </button>
        )}
      </div>
      <CapitalOverviewCards />
      <InvestorTable />
      {showCreate && <CreateInvestorDialog onClose={() => setShowCreate(false)} />}
    </div>
  );
}
