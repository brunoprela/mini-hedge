"use client";

/**
 * Order blotter.
 *
 * Bedrock templates (see design/systems/hedge-fund-desk/02-modules/ui/internal/overview.md):
 * - Section heading shape: tailwind-templates/application-ui-v4/react/headings/section-headings/07-with-actions-and-tabs.jsx
 * - Tab row: tailwind-templates/application-ui-v4/react/navigation/tabs/08-tabs-with-underline-and-badges.jsx
 * - Table body: tailwind-templates/application-ui-v4/react/lists/tables/12-with-condensed-content.jsx
 *
 * Institutional divergences from template:
 * - Rows are tinted by order state (filled=success, cancelled/rejected=destructive, working=primary)
 *   so traders can scan blotter state at a glance. Template has plain rows.
 * - Section heading padding is pb-3 rather than pb-5 (denser desk density).
 * - Responsive md:absolute header positioning dropped (desk UI is fixed-wide).
 */

import { TableSkeleton } from "@mini-hedge/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { StatusDot } from "@/shared/components/charts";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTableState } from "@/shared/hooks/use-table-state";
import { Permission } from "@/shared/lib/permissions";
import type { OrderSummary } from "../types";
import { cancelOrder, ordersQueryOptions } from "../api";
import { AlgoTypeBadge, OrderStateBadge } from "./order-state-badge";

type StatusFilter = "all" | "open" | "filled" | "cancelled" | "rejected";

const STATUS_TABS: { label: string; value: StatusFilter }[] = [
  { label: "All", value: "all" },
  { label: "Open", value: "open" },
  { label: "Filled", value: "filled" },
  { label: "Cancelled", value: "cancelled" },
  { label: "Rejected", value: "rejected" },
];

const OPEN_STATES = new Set([
  "draft",
  "pending_compliance",
  "approved",
  "sent",
  "working",
  "partially_filled",
]);

function stateRowClass(state: string): string {
  switch (state) {
    case "filled":
      return "bg-[var(--success-muted)]";
    case "rejected":
    case "cancelled":
      return "bg-[var(--destructive-muted)]";
    case "working":
    case "partially_filled":
      return "bg-[var(--primary-muted)]";
    default:
      return "";
  }
}

function stateDotVariant(state: string): "success" | "warning" | "error" | "info" | "neutral" {
  switch (state) {
    case "filled":
      return "success";
    case "rejected":
    case "cancelled":
      return "error";
    case "working":
    case "partially_filled":
    case "sent":
      return "info";
    case "pending_compliance":
      return "warning";
    default:
      return "neutral";
  }
}

/** Order states that can be cancelled */
const CANCELLABLE_STATES = new Set([
  "draft",
  "pending_compliance",
  "approved",
  "sent",
  "working",
  "partially_filled",
]);

export function OrderBlotter({
  portfolioId,
  orders: externalOrders,
  portfolioNameMap,
  onSelectOrder,
  selectedOrderId,
}: {
  /** Portfolio ID for single-portfolio mode. Undefined in cross-portfolio mode. */
  portfolioId?: string;
  /** Pre-fetched orders (used in cross-portfolio mode). When provided, skips internal fetch. */
  orders?: OrderSummary[];
  /** Map of portfolio ID → name, shown as a column in cross-portfolio mode. */
  portfolioNameMap?: Map<string, string>;
  onSelectOrder?: (orderId: string | null) => void;
  selectedOrderId?: string | null;
}) {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const queryClient = useQueryClient();
  const { data: fetchedOrders, isLoading } = useQuery({
    ...ordersQueryOptions(fundSlug, portfolioId ?? ""),
    enabled: !!portfolioId,
  });
  const orders = externalOrders ?? fetchedOrders;
  const isCrossPortfolio = !!portfolioNameMap;
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const exportCSV = useExportCSV();

  const canCancel = can(Permission.ORDERS_CANCEL);

  // Optimistic cancel: immediately mark the order as "cancelled" in the cache,
  // then roll back if the server rejects.
  const cancelMutation = useMutation({
    mutationFn: (orderId: string) => cancelOrder(fundSlug, orderId),
    onMutate: async (orderId) => {
      setCancellingId(orderId);
      const queryKey = ["orders", fundSlug, portfolioId ?? ""];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<OrderSummary[]>(queryKey);
      queryClient.setQueryData<OrderSummary[] | undefined>(queryKey, (old) =>
        old?.map((o) => (o.id === orderId ? { ...o, state: "cancelled" } : o)),
      );
      return { previous, queryKey };
    },
    onSuccess: () => {
      toast.success("Order cancelled");
    },
    onError: (err: Error, _orderId, context) => {
      if (context?.previous && context.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
      toast.error(`Cancel failed: ${err.message}`);
    },
    onSettled: () => {
      setCancellingId(null);
      queryClient.invalidateQueries({ queryKey: ["orders", fundSlug] });
    },
  });

  const tabCounts = useMemo<Record<StatusFilter, number>>(() => {
    const base: Record<StatusFilter, number> = {
      all: 0,
      open: 0,
      filled: 0,
      cancelled: 0,
      rejected: 0,
    };
    if (!orders) return base;
    base.all = orders.length;
    for (const o of orders) {
      if (OPEN_STATES.has(o.state)) base.open += 1;
      else if (o.state === "filled") base.filled += 1;
      else if (o.state === "cancelled") base.cancelled += 1;
      else if (o.state === "rejected") base.rejected += 1;
    }
    return base;
  }, [orders]);

  const filteredOrders = useMemo(() => {
    if (!orders) return [];
    switch (statusFilter) {
      case "open":
        return orders.filter((o) => OPEN_STATES.has(o.state));
      case "filled":
        return orders.filter((o) => o.state === "filled");
      case "cancelled":
        return orders.filter((o) => o.state === "cancelled");
      case "rejected":
        return orders.filter((o) => o.state === "rejected");
      default:
        return orders;
    }
  }, [orders, statusFilter]);

  const table = useTableState({
    data: filteredOrders as unknown as Record<string, unknown>[],
    initialSort: { key: "created_at", direction: "desc" },
    pageSize: 20,
    searchKeys: ["id", "instrument_id", "side", "state", ...(isCrossPortfolio ? ["portfolio_id"] : [])],
  });

  const handleExport = () => {
    if (!filteredOrders || filteredOrders.length === 0) return;
    const exportData = filteredOrders.map((o) => ({
      ...(isCrossPortfolio
        ? { portfolio: portfolioNameMap?.get(o.portfolio_id) ?? o.portfolio_id }
        : {}),
      instrument: o.instrument_id,
      side: o.side,
      type: o.order_type,
      quantity: o.quantity,
      limit_price: o.limit_price ?? "",
      filled_quantity: o.filled_quantity,
      avg_fill_price: o.avg_fill_price ?? "",
      time_in_force: o.time_in_force ?? "",
      broker_id: o.broker_id ?? "",
      state: o.state,
      created_at: o.created_at,
    }));
    exportCSV(
      exportData as unknown as Record<string, unknown>[],
      isCrossPortfolio ? "orders-all-portfolios" : `orders-${portfolioId}`,
    );
  };

  if (isLoading) {
    return <TableSkeleton rows={6} columns={isCrossPortfolio ? 8 : 7} />;
  }

  if (!orders || orders.length === 0) {
    return <div className="text-sm text-[var(--muted-foreground)]">No orders yet.</div>;
  }

  return (
    <div className="space-y-4">
      {/* Section heading — template: headings/section-headings/07-with-actions-and-tabs.jsx */}
      <div className="border-b border-[var(--border)] pb-3">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-base font-semibold text-[var(--foreground-bright)]">Order Blotter</h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--muted-foreground)]">
              {table.totalFiltered} results
            </span>
            <div className="w-56">
              <TableSearch
                value={table.search}
                onChange={table.setSearch}
                placeholder="Search orders..."
              />
            </div>
            <button
              type="button"
              onClick={handleExport}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--card)] px-3 py-2 text-sm font-semibold text-[var(--foreground)] inset-ring inset-ring-[var(--border)] hover:bg-[var(--muted)]"
            >
              <Download className="h-4 w-4" />
              Export
            </button>
          </div>
        </div>
        {/* Tabs — template: navigation/tabs/08-tabs-with-underline-and-badges.jsx */}
        <div className="mt-3">
          <nav aria-label="Order status tabs" className="-mb-px flex space-x-8">
            {STATUS_TABS.map((tab) => {
              const isActive = statusFilter === tab.value;
              return (
                <button
                  key={tab.value}
                  type="button"
                  aria-current={isActive ? "page" : undefined}
                  onClick={() => {
                    setStatusFilter(tab.value);
                    table.setPage(0);
                  }}
                  className={`flex border-b-2 px-1 pb-3 text-sm font-medium whitespace-nowrap ${
                    isActive
                      ? "border-[var(--primary)] text-[var(--primary)]"
                      : "border-transparent text-[var(--muted-foreground)] hover:border-[var(--border-bright)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {tab.label}
                  <span
                    className={`ml-3 hidden rounded-full px-2.5 py-0.5 text-xs font-medium md:inline-block ${
                      isActive
                        ? "bg-[var(--primary-muted)] text-[var(--primary)]"
                        : "bg-[var(--muted)] text-[var(--foreground)]"
                    }`}
                  >
                    {tabCounts[tab.value]}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Table — template: lists/tables/12-with-condensed-content.jsx */}
      <div className="overflow-x-auto">
        <table className="relative min-w-full divide-y divide-[var(--table-border)]">
          <thead>
            <tr>
              <SortableHeader
                label="Instrument"
                sortKey="instrument_id"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              {isCrossPortfolio && (
                <SortableHeader
                  label="Portfolio"
                  sortKey="portfolio_id"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
              )}
              <SortableHeader
                label="Side"
                sortKey="side"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Type"
                sortKey="order_type"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Qty"
                sortKey="quantity"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Filled"
                sortKey="filled_quantity"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Limit"
                sortKey="limit_price"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Avg Fill"
                sortKey="avg_fill_price"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="TIF"
                sortKey="time_in_force"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Broker"
                sortKey="broker_id"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="State"
                sortKey="state"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Time"
                sortKey="created_at"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <th scope="col" className="py-2 pr-4 pl-3 whitespace-nowrap">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)] bg-[var(--card)]">
            {table.rows.map((row) => {
              const order = row as Record<string, unknown>;
              const state = order.state as string;
              const isCancellable = CANCELLABLE_STATES.has(state);
              const orderId = order.id as string;
              const isSelected = selectedOrderId === orderId;

              return (
                <tr
                  key={orderId}
                  onClick={() => onSelectOrder?.(isSelected ? null : orderId)}
                  className={`${stateRowClass(state)} hover:bg-[var(--table-row-hover)] ${
                    onSelectOrder ? "cursor-pointer" : ""
                  } ${isSelected ? "ring-1 ring-inset ring-[var(--primary)]" : ""}`}
                >
                  <td className="px-2 py-2 pl-4 text-sm whitespace-nowrap font-medium text-[var(--foreground)]">
                    <span className="flex items-center gap-2">
                      <StatusDot variant={stateDotVariant(state)} size={7} />
                      {order.parent_order_id ? (
                        <span
                          className="text-[10px] text-[var(--muted-foreground)]"
                          title={`Child of ${order.parent_order_id as string}`}
                        >
                          ↳
                        </span>
                      ) : null}
                      <span>{order.instrument_id as string}</span>
                      {order.algo_type ? (
                        <AlgoTypeBadge algoType={order.algo_type as string} />
                      ) : null}
                    </span>
                  </td>
                  {isCrossPortfolio && (
                    <td className="px-2 py-2 text-xs whitespace-nowrap text-[var(--muted-foreground)]">
                      {portfolioNameMap?.get(order.portfolio_id as string) ??
                        (order.portfolio_id as string)}
                    </td>
                  )}
                  <td className="px-2 py-2 text-sm whitespace-nowrap">
                    <span
                      className={`text-xs font-medium uppercase ${
                        (order.side as string) === "buy"
                          ? "text-[var(--success)]"
                          : "text-[var(--destructive)]"
                      }`}
                    >
                      {(order.side as string).toUpperCase()}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-sm whitespace-nowrap text-[var(--muted-foreground)]">
                    {order.order_type as string}
                  </td>
                  <td className="px-2 py-2 text-right font-mono text-sm whitespace-nowrap text-[var(--foreground)]">
                    {parseFloat(order.quantity as string).toLocaleString()}
                  </td>
                  <td className="px-2 py-2 text-right font-mono text-sm whitespace-nowrap text-[var(--foreground)]">
                    {parseFloat(order.filled_quantity as string).toLocaleString()}
                    {order.is_parent && Number(order.children_count) > 0 ? (
                      <span className="ml-1 text-[10px] text-[var(--muted-foreground)]">
                        ({Number(order.children_filled)}/{Number(order.children_count)} slices)
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-2 text-right font-mono text-sm whitespace-nowrap text-[var(--muted-foreground)]">
                    {order.limit_price
                      ? `$${parseFloat(order.limit_price as string).toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td className="px-2 py-2 text-right font-mono text-sm whitespace-nowrap text-[var(--muted-foreground)]">
                    {order.avg_fill_price
                      ? `$${parseFloat(order.avg_fill_price as string).toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td className="px-2 py-2 text-xs whitespace-nowrap uppercase text-[var(--muted-foreground)]">
                    {(order.time_in_force as string) ?? "\u2014"}
                  </td>
                  <td className="px-2 py-2 text-xs whitespace-nowrap text-[var(--muted-foreground)]">
                    {(order.broker_id as string) ?? "\u2014"}
                  </td>
                  <td className="px-2 py-2 whitespace-nowrap">
                    <OrderStateBadge state={state} />
                  </td>
                  <td className="px-2 py-2 text-xs whitespace-nowrap text-[var(--muted-foreground)]">
                    {new Date(order.created_at as string).toLocaleTimeString(undefined, {
                      timeZoneName: "short",
                    })}
                  </td>
                  <td className="py-2 pr-4 pl-3 text-right text-sm font-medium whitespace-nowrap">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/${fundSlug}/orders/${orderId}/tca`}
                        className="text-[var(--primary)] hover:text-[var(--foreground-bright)]"
                      >
                        {state === "filled" ? "TCA" : "Details"}
                        <span className="sr-only">, {order.instrument_id as string}</span>
                      </Link>
                      {isCancellable && canCancel && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            cancelMutation.mutate(orderId);
                          }}
                          disabled={cancellingId === orderId}
                          className="text-[var(--destructive)] hover:text-[var(--foreground-bright)] disabled:opacity-40"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {table.totalPages > 1 && (
        <TablePagination
          page={table.page}
          totalPages={table.totalPages}
          totalItems={table.totalFiltered}
          pageSize={table.pageSize}
          onPageChange={table.setPage}
        />
      )}
    </div>
  );
}
