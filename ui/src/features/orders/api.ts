import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type {
  CreateAlgoOrderRequest,
  CreateBlockAllocationRequest,
  CreateOrderRequest,
} from "./types";

export function ordersQueryOptions(fundSlug: string, portfolioId: string) {
  return queryOptions({
    queryKey: ["orders", fundSlug, portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/orders", {
        params: { query: { portfolio_id: portfolioId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 60_000,
  });
}

export function orderFillsQueryOptions(fundSlug: string, orderId: string) {
  return queryOptions({
    queryKey: ["order-fills", fundSlug, orderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/orders/{order_id}/fills", {
        params: { path: { order_id: orderId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
  });
}

export function orderChildrenQueryOptions(fundSlug: string, orderId: string) {
  return queryOptions({
    queryKey: ["order-children", fundSlug, orderId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/orders/{order_id}/children", {
        params: { path: { order_id: orderId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 10_000,
  });
}

export async function createOrder(fundSlug: string, order: CreateOrderRequest) {
  const { data, error } = await api.POST("/api/v1/orders", {
    body: order,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data;
}

export async function createAlgoOrder(fundSlug: string, order: CreateAlgoOrderRequest) {
  const { data, error } = await api.POST("/api/v1/orders/algo", {
    body: order,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data;
}

export async function cancelOrder(fundSlug: string, orderId: string) {
  const { data, error } = await api.POST("/api/v1/orders/{order_id}/cancel", {
    params: { path: { order_id: orderId } },
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data;
}

// Block allocation API

export async function createBlockAllocation(
  fundSlug: string,
  request: CreateBlockAllocationRequest,
) {
  const { data, error } = await api.POST("/api/v1/allocations", {
    body: request,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data;
}

export function allocationQueryOptions(fundSlug: string, allocationId: string) {
  return queryOptions({
    queryKey: ["allocation", fundSlug, allocationId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allocations/{allocation_id}", {
        params: { path: { allocation_id: allocationId } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    staleTime: 10_000,
  });
}

export async function cancelBlockAllocation(fundSlug: string, allocationId: string) {
  const { data, error } = await api.POST("/api/v1/allocations/{allocation_id}/cancel", {
    params: { path: { allocation_id: allocationId } },
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data;
}
