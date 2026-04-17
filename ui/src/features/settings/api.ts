import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type {
  ApiKey,
  ApiKeyCreateRequest,
  ApiKeyCreateResponse,
  AuditLogEntry,
  AuditLogResponse,
} from "./types";

export function apiKeysQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["api-keys", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/api-keys", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return (data ?? []) as unknown as ApiKey[];
    },
    staleTime: 60_000,
  });
}

export async function createApiKey(fundSlug: string, payload: ApiKeyCreateRequest) {
  const { data, error } = await api.POST("/api/v1/api-keys", {
    body: payload as never,
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
  return data as ApiKeyCreateResponse;
}

export async function revokeApiKey(fundSlug: string, keyId: string) {
  const { error } = await api.DELETE("/api/v1/api-keys/{key_id}", {
    params: { path: { key_id: keyId } },
    headers: fundHeaders(fundSlug),
  });
  if (error) throw error;
}

/* ------------------------------------------------------------------ */
/*  Audit / Activity Log                                               */
/* ------------------------------------------------------------------ */

/**
 * The backend `/admin/audit` endpoint returns an `AuditPage` of `AuditEntry`
 * records (event-sourced shape: `event_type`, `payload`, `created_at`). The
 * UI's `ActivityLog` component expects the flatter `AuditLogEntry` shape
 * (`action`, `description`, `timestamp`, optional `ip_address`/`user_agent`).
 * Adapt the backend response in-place so callers can keep using the local
 * types unchanged.
 */
export function activityLogQueryOptions(
  fundSlug: string,
  params: { limit: number; offset: number; actionType?: string },
) {
  return queryOptions({
    queryKey: ["audit-log", fundSlug, params.limit, params.offset, params.actionType ?? "all"],
    queryFn: async (): Promise<AuditLogResponse> => {
      const { data, error } = await api.GET("/api/v1/admin/audit", {
        params: {
          query: {
            fund_slug: fundSlug,
            event_type: params.actionType,
            limit: params.limit,
            offset: params.offset,
          },
        },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      const page = data!;
      const entries: AuditLogEntry[] = page.items.map((item) => {
        const payload = (item.payload ?? {}) as Record<string, unknown>;
        return {
          id: item.id,
          timestamp: item.created_at,
          action: item.event_type,
          description:
            typeof payload.description === "string"
              ? (payload.description as string)
              : typeof payload.message === "string"
                ? (payload.message as string)
                : item.event_type.replace(/_/g, " "),
          ip_address:
            typeof payload.ip_address === "string" ? (payload.ip_address as string) : undefined,
          user_agent:
            typeof payload.user_agent === "string" ? (payload.user_agent as string) : undefined,
          metadata: payload,
        };
      });
      return {
        entries,
        total: page.total,
        has_more: page.offset + page.items.length < page.total,
      };
    },
    staleTime: 30_000,
  });
}
