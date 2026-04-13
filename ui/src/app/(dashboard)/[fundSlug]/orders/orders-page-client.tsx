"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { ordersQueryOptions } from "@/features/orders/api";
import { BlockAllocationDialog } from "@/features/orders/components/block-allocation-dialog";
import { OrderBlotter } from "@/features/orders/components/order-blotter";
import { OrderDetailPanel } from "@/features/orders/components/order-detail-panel";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { ALL_PORTFOLIOS, PortfolioSelector } from "@/shared/components/portfolio-selector";
import { useTradeTicket } from "@/shared/components/trade-ticket-provider";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";

export function OrdersPageClient() {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const { openTradeTicket } = useTradeTicket();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [showBlockAllocation, setShowBlockAllocation] = useState(false);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";
  const isAllPortfolios = activePortfolioId === ALL_PORTFOLIOS;

  // Single-portfolio fetch (used when a specific portfolio is selected)
  const { data: singlePortfolioOrders } = useQuery({
    ...ordersQueryOptions(fundSlug, activePortfolioId),
    enabled: !!activePortfolioId && !isAllPortfolios,
  });

  // Multi-portfolio fetch (used when "All Portfolios" is selected)
  const allPortfolioQueries = useQueries({
    queries:
      isAllPortfolios && portfolios
        ? portfolios.map((p) => ({
            ...ordersQueryOptions(fundSlug, p.id),
          }))
        : [],
  });

  // Merge orders from all portfolios when in cross-portfolio mode
  const orders = useMemo(() => {
    if (!isAllPortfolios) return singlePortfolioOrders ?? undefined;
    const merged = allPortfolioQueries.flatMap((q) => q.data ?? []);
    return merged.length > 0 || allPortfolioQueries.every((q) => q.isSuccess)
      ? merged
      : undefined;
  }, [isAllPortfolios, singlePortfolioOrders, allPortfolioQueries]);

  // Portfolio name lookup for cross-portfolio mode
  const portfolioNameMap = useMemo(() => {
    if (!portfolios) return undefined;
    const map = new Map<string, string>();
    for (const p of portfolios) {
      map.set(p.id, p.name);
    }
    return map;
  }, [portfolios]);

  // Summary metrics
  const summary = useMemo(() => {
    if (!orders) return null;
    const working = orders.filter((o) =>
      [
        "pending",
        "pending_compliance",
        "approved",
        "sent",
        "working",
        "partially_filled",
        "draft",
      ].includes(o.state),
    );
    const filled = orders.filter((o) => o.state === "filled");
    const rejected = orders.filter((o) => o.state === "rejected");
    const totalNotional = orders.reduce((sum, o) => {
      const price = Number(o.avg_fill_price || o.limit_price || 0);
      return sum + Number(o.quantity) * price;
    }, 0);

    return {
      total: orders.length,
      working: working.length,
      filled: filled.length,
      rejected: rejected.length,
      notional: totalNotional,
      fillRate: orders.length > 0 ? ((filled.length / orders.length) * 100).toFixed(0) : "0",
    };
  }, [orders]);

  const selectedOrder = useMemo(() => {
    if (!selectedOrderId || !orders) return null;
    return orders.find((o) => o.id === selectedOrderId) ?? null;
  }, [selectedOrderId, orders]);

  return (
    <div className="space-y-3">
      {/* Header toolbar */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Orders</h1>
        <div className="flex items-center gap-2">
          {can(Permission.ORDERS_CREATE) && (
            <button
              type="button"
              onClick={() => setShowBlockAllocation(true)}
              className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
            >
              Block Allocation
            </button>
          )}
          {can(Permission.TRADES_EXECUTE) && !isAllPortfolios && (
            <button
              type="button"
              onClick={() => openTradeTicket({ portfolioId: activePortfolioId })}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
            >
              <Plus className="h-3.5 w-3.5" />
              New Order
            </button>
          )}
          {portfolios && (
            <PortfolioSelector
              portfolios={portfolios}
              value={activePortfolioId}
              onChange={setSelectedPortfolioId}
              showAllOption
            />
          )}
        </div>
      </div>

      {/* Summary strip */}
      {summary && (
        <div className="flex items-center gap-4 rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-2">
          <SummaryItem label="Total" value={String(summary.total)} />
          <Divider />
          <SummaryItem label="Working" value={String(summary.working)} color="var(--primary)" />
          <Divider />
          <SummaryItem label="Filled" value={String(summary.filled)} color="var(--success)" />
          <Divider />
          <SummaryItem
            label="Rejected"
            value={String(summary.rejected)}
            color="var(--destructive)"
          />
          <Divider />
          <SummaryItem label="Fill Rate" value={`${summary.fillRate}%`} />
          <Divider />
          <SummaryItem
            label="Notional"
            value={summary.notional > 0 ? `$${(summary.notional / 1_000_000).toFixed(1)}M` : "$0"}
          />
        </div>
      )}

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      {/* Main area: blotter + optional detail panel */}
      <div className="flex gap-3">
        <div className="min-w-0 flex-1">
          {(activePortfolioId || isAllPortfolios) && (
            <OrderBlotter
              portfolioId={isAllPortfolios ? undefined : activePortfolioId}
              orders={orders}
              portfolioNameMap={isAllPortfolios ? portfolioNameMap : undefined}
              onSelectOrder={setSelectedOrderId}
              selectedOrderId={selectedOrderId}
            />
          )}
        </div>

        {/* Order detail side panel */}
        {selectedOrder && (
          <OrderDetailPanel
            order={selectedOrder}
            onClose={() => setSelectedOrderId(null)}
            onClone={(o) => {
              openTradeTicket({
                instrument: o.instrument_id,
                side: o.side as "buy" | "sell",
                quantity: o.quantity,
                portfolioId: isAllPortfolios ? o.portfolio_id : activePortfolioId,
              });
            }}
          />
        )}
      </div>

      <BlockAllocationDialog
        open={showBlockAllocation}
        onClose={() => setShowBlockAllocation(false)}
      />
    </div>
  );
}

function SummaryItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <p className="font-mono text-sm font-bold" style={color ? { color } : undefined}>
        {value}
      </p>
      <p className="text-[9px] uppercase tracking-wider text-[var(--muted-foreground)]">{label}</p>
    </div>
  );
}

function Divider() {
  return <div className="h-6 w-px bg-[var(--border)]" />;
}
