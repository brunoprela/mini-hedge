import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";
import type { ApiKey, ApiKeyCreateRequest, ApiKeyCreateResponse, AuditLogResponse } from "./types";

export function apiKeysQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["api-keys", fundSlug],
    queryFn: () => clientFetch<ApiKey[]>("/api-keys", { fundSlug }),
    staleTime: 60_000,
  });
}

export function createApiKey(fundSlug: string, payload: ApiKeyCreateRequest) {
  return clientFetch<ApiKeyCreateResponse>("/api-keys", {
    fundSlug,
    method: "POST",
    body: payload,
  });
}

export function revokeApiKey(fundSlug: string, keyId: string) {
  return clientFetch<void>(`/api-keys/${keyId}`, {
    fundSlug,
    method: "DELETE",
  });
}

/* ------------------------------------------------------------------ */
/*  Audit / Activity Log                                               */
/* ------------------------------------------------------------------ */

export function activityLogQueryOptions(
  fundSlug: string,
  params: { limit: number; offset: number; actionType?: string },
) {
  const search = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  if (params.actionType) search.set("action_type", params.actionType);

  return queryOptions({
    queryKey: ["audit-log", fundSlug, params.limit, params.offset, params.actionType ?? "all"],
    queryFn: () =>
      clientFetch<AuditLogResponse>(`/audit-log?${search.toString()}`, { fundSlug }),
    staleTime: 30_000,
  });
}
