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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Corporate Actions</h1>
        {canProcess && (
          <button
            type="button"
            onClick={() => setShowDialog(true)}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-colors hover:brightness-110"
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
