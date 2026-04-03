"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { ordersQueryOptions } from "../api";
import { OrderStateBadge } from "./order-state-badge";

export function OrderBlotter({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: orders, isLoading } = useQuery(ordersQueryOptions(fundSlug, portfolioId));

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading orders...</div>;
  }

  if (!orders || orders.length === 0) {
    return <div className="text-sm text-[var(--muted-foreground)]">No orders yet.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-[var(--muted-foreground)]">
            <th className="pb-2 pr-4">Instrument</th>
            <th className="pb-2 pr-4">Side</th>
            <th className="pb-2 pr-4">Type</th>
            <th className="pb-2 pr-4 text-right">Qty</th>
            <th className="pb-2 pr-4 text-right">Filled</th>
            <th className="pb-2 pr-4 text-right">Avg Price</th>
            <th className="pb-2 pr-4">State</th>
            <th className="pb-2">Time</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id} className="border-b last:border-0">
              <td className="py-2 pr-4 font-medium">{order.instrument_id}</td>
              <td className="py-2 pr-4">
                <span className={order.side === "buy" ? "text-green-600" : "text-red-600"}>
                  {order.side.toUpperCase()}
                </span>
              </td>
              <td className="py-2 pr-4">{order.order_type}</td>
              <td className="py-2 pr-4 text-right">
                {parseFloat(order.quantity).toLocaleString()}
              </td>
              <td className="py-2 pr-4 text-right">
                {parseFloat(order.filled_quantity).toLocaleString()}
              </td>
              <td className="py-2 pr-4 text-right">
                {order.avg_fill_price
                  ? `$${parseFloat(order.avg_fill_price).toFixed(2)}`
                  : "\u2014"}
              </td>
              <td className="py-2 pr-4">
                <OrderStateBadge state={order.state} />
              </td>
              <td className="py-2 text-xs text-[var(--muted-foreground)]">
                {new Date(order.created_at).toLocaleTimeString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
