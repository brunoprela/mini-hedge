import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { CreateOrderRequest, FillDetail, OrderSummary } from "./types";

export function ordersQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["orders", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<OrderSummary[]>(`/orders?portfolio_id=${portfolioId}`, {
        fundSlug,
      }),
    refetchInterval: 10_000,
  });
}

export function orderFillsQueryOptions(fundSlug: string, orderId: string) {
  return queryOptions({
    queryKey: ["order-fills", fundSlug, orderId],
    queryFn: () => clientFetch<FillDetail[]>(`/orders/${orderId}/fills`, { fundSlug }),
  });
}

export async function createOrder(
  fundSlug: string,
  order: CreateOrderRequest,
): Promise<OrderSummary> {
  return clientFetch<OrderSummary>("/orders", {
    fundSlug,
    method: "POST",
    body: order,
  });
}

export async function cancelOrder(fundSlug: string, orderId: string): Promise<OrderSummary> {
  return clientFetch<OrderSummary>(`/orders/${orderId}/cancel`, {
    fundSlug,
    method: "POST",
  });
}
