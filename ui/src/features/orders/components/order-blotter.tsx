"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { StatusDot } from "@/shared/components/charts";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
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

export function OrderBlotter({
  portfolioId,
  onSelectOrder,
  selectedOrderId,
}: {
  portfolioId: string;
  onSelectOrder?: (orderId: string | null) => void;
  selectedOrderId?: string | null;
}) {
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
      limit_price: o.limit_price ?? "",
      filled_quantity: o.filled_quantity,
      avg_fill_price: o.avg_fill_price ?? "",
      time_in_force: o.time_in_force ?? "",
      broker_id: o.broker_id ?? "",
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
      <SectionPanel
        title="Order Blotter"
        tabs={STATUS_TABS.map((tab) => (
          <ToolbarTab
            key={tab.value}
            label={tab.label}
            active={statusFilter === tab.value}
            onClick={() => {
              setStatusFilter(tab.value);
              table.setPage(0);
            }}
          />
        ))}
        actions={
          <>
            <span className="text-[10px] font-medium text-[var(--muted-foreground)]">
              {table.totalFiltered} results
            </span>
            <div className="w-48">
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
              className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
            >
              <Download className="h-3.5 w-3.5" />
              CSV
            </button>
          </>
        }
      >
        <div className="overflow-x-auto">
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
                <th className="w-10 px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => {
                const order = row as Record<string, unknown>;
                const state = order.state as string;
                const isCancellable = CANCELLABLE_STATES.has(state);
                const orderId = order.id as string;

                return (
                  <tr
                    key={orderId}
                    onClick={() => onSelectOrder?.(selectedOrderId === orderId ? null : orderId)}
                    className={`border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)] ${stateRowClass(state)} ${onSelectOrder ? "cursor-pointer" : ""} ${selectedOrderId === orderId ? "ring-1 ring-inset ring-[var(--primary)]" : ""}`}
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
                      {order.limit_price
                        ? `$${parseFloat(order.limit_price as string).toFixed(2)}`
                        : "\u2014"}
                    </td>
                    <td className="px-3 py-2 pr-4 text-right font-mono">
                      {order.avg_fill_price
                        ? `$${parseFloat(order.avg_fill_price as string).toFixed(2)}`
                        : "\u2014"}
                    </td>
                    <td className="px-3 py-2 pr-4 text-xs uppercase text-[var(--muted-foreground)]">
                      {(order.time_in_force as string) ?? "\u2014"}
                    </td>
                    <td className="px-3 py-2 pr-4 text-xs text-[var(--muted-foreground)]">
                      {(order.broker_id as string) ?? "\u2014"}
                    </td>
                    <td className="px-3 py-2 pr-4">
                      <OrderStateBadge state={state} />
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
                      {new Date(order.created_at as string).toLocaleTimeString(undefined, {
                        timeZoneName: "short",
                      })}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <Link
                          href={`/${fundSlug}/orders/${orderId}/tca`}
                          className="rounded px-1.5 py-0.5 text-[10px] font-medium text-[var(--primary)] transition-colors hover:bg-[var(--primary-muted)]"
                        >
                          {state === "filled" ? "TCA" : "Details"}
                        </Link>
                        {isCancellable && canCancel && (
                          <button
                            type="button"
                            onClick={() => cancelMutation.mutate(orderId)}
                            disabled={cancellingId === orderId}
                            className="rounded px-1.5 py-0.5 text-[10px] font-medium text-[var(--destructive)] transition-colors hover:bg-[var(--destructive-muted)] disabled:opacity-40"
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
      </SectionPanel>

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
