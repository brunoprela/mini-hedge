"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { StatusDot } from "@/shared/components/charts";
import { QuickActions, type QuickAction } from "@/shared/components/quick-actions";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTableState } from "@/shared/hooks/use-table-state";
import { Permission } from "@/shared/lib/permissions";
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

export function OrderBlotter({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const queryClient = useQueryClient();
  const { data: orders, isLoading } = useQuery(ordersQueryOptions(fundSlug, portfolioId));
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const exportCSV = useExportCSV();

  const canCancel = can(Permission.ORDERS_CANCEL);

  const cancelMutation = useMutation({
    mutationFn: (orderId: string) => cancelOrder(fundSlug, orderId),
    onMutate: (orderId) => setCancellingId(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders", fundSlug, portfolioId] });
      toast.success("Order cancelled");
    },
    onError: (err: Error) => {
      toast.error(`Cancel failed: ${err.message}`);
    },
    onSettled: () => setCancellingId(null),
  });

  const filteredOrders = useMemo(() => {
    if (!orders) return [];
    switch (statusFilter) {
      case "open":
        return orders.filter(
          (o) =>
            o.state === "draft" ||
            o.state === "pending_compliance" ||
            o.state === "approved" ||
            o.state === "sent" ||
            o.state === "working" ||
            o.state === "partially_filled",
        );
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
    searchKeys: ["instrument_id", "side", "state"],
  });

  const handleExport = () => {
    if (!filteredOrders || filteredOrders.length === 0) return;
    const exportData = filteredOrders.map((o) => ({
      instrument: o.instrument_id,
      side: o.side,
      type: o.order_type,
      quantity: o.quantity,
      filled_quantity: o.filled_quantity,
      avg_fill_price: o.avg_fill_price ?? "",
      state: o.state,
      created_at: o.created_at,
    }));
    exportCSV(exportData as unknown as Record<string, unknown>[], `orders-${portfolioId}`);
  };

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading orders...</div>;
  }

  if (!orders || orders.length === 0) {
    return <div className="text-sm text-[var(--muted-foreground)]">No orders yet.</div>;
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4">
        {/* Status filter tabs */}
        <div className="flex items-center gap-1">
          {STATUS_TABS.map((tab) => (
            <button
              type="button"
              key={tab.value}
              onClick={() => {
                setStatusFilter(tab.value);
                table.setPage(0);
              }}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                statusFilter === tab.value
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search + Export */}
        <div className="flex items-center gap-2">
          <div className="w-64">
            <TableSearch
              value={table.search}
              onChange={table.setSearch}
              placeholder="Search orders..."
            />
          </div>
          <button
            type="button"
            onClick={handleExport}
            title="Export to CSV"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-[var(--muted-foreground)]">
              <SortableHeader
                label="Instrument"
                sortKey="instrument_id"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
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
                label="Avg Price"
                sortKey="avg_fill_price"
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
              <th className="w-10 px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => {
              const order = row as Record<string, unknown>;
              const state = order.state as string;
              const isCancellable = CANCELLABLE_STATES.has(state);
              const orderId = order.id as string;

              const actions: QuickAction[] = [
                {
                  label: "View Details",
                  onClick: () => window.location.assign(`/${fundSlug}/orders/${orderId}/tca`),
                },
              ];
              if (state === "filled") {
                actions.push({
                  label: "View TCA",
                  variant: "primary",
                  onClick: () => window.location.assign(`/${fundSlug}/orders/${orderId}/tca`),
                });
              }
              if (isCancellable && canCancel) {
                actions.push({
                  label: "Cancel Order",
                  variant: "danger",
                  onClick: () => cancelMutation.mutate(orderId),
                  disabled: cancellingId === orderId,
                });
              }

              return (
                <tr
                  key={orderId}
                  className={`border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)] ${stateRowClass(state)}`}
                >
                  <td className="px-3 py-2 pr-4 font-medium">
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
                      <span className="text-[var(--foreground)]">
                        {order.instrument_id as string}
                      </span>
                      {order.algo_type ? (
                        <AlgoTypeBadge algoType={order.algo_type as string} />
                      ) : null}
                    </span>
                  </td>
                  <td className="px-3 py-2 pr-4">
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
                  <td className="px-3 py-2 pr-4">{order.order_type as string}</td>
                  <td className="px-3 py-2 pr-4 text-right font-mono">
                    {parseFloat(order.quantity as string).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 pr-4 text-right font-mono">
                    {parseFloat(order.filled_quantity as string).toLocaleString()}
                    {order.is_parent && Number(order.children_count) > 0 ? (
                      <span className="ml-1 text-[10px] text-[var(--muted-foreground)]">
                        ({Number(order.children_filled)}/{Number(order.children_count)} slices)
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 pr-4 text-right font-mono">
                    {order.avg_fill_price
                      ? `$${parseFloat(order.avg_fill_price as string).toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td className="px-3 py-2 pr-4">
                    <OrderStateBadge state={state} />
                  </td>
                  <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
                    {new Date(order.created_at as string).toLocaleTimeString()}
                  </td>
                  <td className="px-3 py-2">
                    <QuickActions actions={actions} />
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
