"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { BlockAllocationDialog } from "@/features/orders/components/block-allocation-dialog";
import { OrderBlotter } from "@/features/orders/components/order-blotter";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";

export function OrdersPageClient() {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [showBlockAllocation, setShowBlockAllocation] = useState(false);

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-3">
      {/* Header toolbar */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Orders</h1>
        <div className="flex items-center gap-2">
          {/* Portfolio selector */}
          {portfolios && (
            <PortfolioSelector
              portfolios={portfolios}
              value={activePortfolioId}
              onChange={setSelectedPortfolioId}
            />
          )}
        </div>
      </div>

      {/* Quick Actions toolbar */}
      <div className="flex items-center gap-2">
        {can(Permission.TRADES_EXECUTE) && activePortfolioId && (
          <a
            href={`/${fundSlug}/portfolio/${activePortfolioId}?tab=positions&trade_instrument=`}
            className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
          >
            New Order
          </a>
        )}
        {can(Permission.ORDERS_CREATE) && (
          <button
            type="button"
            onClick={() => setShowBlockAllocation(true)}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
          >
            Block Allocation
          </button>
        )}
      </div>

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      {activePortfolioId && <OrderBlotter portfolioId={activePortfolioId} />}

      {showBlockAllocation && (
        <BlockAllocationDialog onClose={() => setShowBlockAllocation(false)} />
      )}
    </div>
  );
}
