import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type {
  BlockAllocationSummary,
  CreateAlgoOrderRequest,
  CreateBlockAllocationRequest,
  CreateOrderRequest,
  FillDetail,
  OrderSummary,
} from "./types";

export function ordersQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["orders", fundSlug, portfolioId],
    queryFn: () =>
      clientFetch<OrderSummary[]>(`/orders?portfolio_id=${portfolioId}`, {
        fundSlug,
      }),
    staleTime: 60_000,
  });
}

export function orderFillsQueryOptions(fundSlug: string, orderId: string) {
  return queryOptions({
    queryKey: ["order-fills", fundSlug, orderId],
    queryFn: () => clientFetch<FillDetail[]>(`/orders/${orderId}/fills`, { fundSlug }),
  });
}

export function orderChildrenQueryOptions(fundSlug: string, orderId: string) {
  return queryOptions({
    queryKey: ["order-children", fundSlug, orderId],
    queryFn: () => clientFetch<OrderSummary[]>(`/orders/${orderId}/children`, { fundSlug }),
    staleTime: 10_000,
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

export async function createAlgoOrder(
  fundSlug: string,
  order: CreateAlgoOrderRequest,
): Promise<OrderSummary> {
  return clientFetch<OrderSummary>("/orders/algo", {
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

// Block allocation API

export async function createBlockAllocation(
  fundSlug: string,
  request: CreateBlockAllocationRequest,
): Promise<BlockAllocationSummary> {
  return clientFetch<BlockAllocationSummary>("/allocations", {
    fundSlug,
    method: "POST",
    body: request,
  });
}

export function allocationQueryOptions(fundSlug: string, allocationId: string) {
  return queryOptions({
    queryKey: ["allocation", fundSlug, allocationId],
    queryFn: () =>
      clientFetch<BlockAllocationSummary>(`/allocations/${allocationId}`, { fundSlug }),
    staleTime: 10_000,
  });
}

export async function cancelBlockAllocation(
  fundSlug: string,
  allocationId: string,
): Promise<BlockAllocationSummary> {
  return clientFetch<BlockAllocationSummary>(`/allocations/${allocationId}/cancel`, {
    fundSlug,
    method: "POST",
  });
}
