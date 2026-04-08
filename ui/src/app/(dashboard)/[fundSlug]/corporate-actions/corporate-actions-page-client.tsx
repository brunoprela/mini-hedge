"use client";

import { useState } from "react";
import { CorporateActionsTable } from "@/features/corporate-actions/components/corporate-actions-table";
import { ProcessActionsDialog } from "@/features/corporate-actions/components/process-actions-dialog";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";

export function CorporateActionsPageClient() {
  const [showDialog, setShowDialog] = useState(false);
  const { can } = usePermission();

  const canProcess = can(Permission.POSITIONS_WRITE);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Corporate Actions</h1>
        {canProcess && (
          <button
            type="button"
            onClick={() => setShowDialog(true)}
            className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
          >
            + Process Actions
          </button>
        )}
      </div>

      <CorporateActionsTable />

      {showDialog && <ProcessActionsDialog onClose={() => setShowDialog(false)} />}
    </div>
  );
}
