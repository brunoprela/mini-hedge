/* ------------------------------------------------------------------ */
/*  API Keys                                                           */
/* ------------------------------------------------------------------ */

export interface ApiKey {
  id: string;
  name: string;
  key_hint: string;
  scopes: string[];
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreateRequest {
  name: string;
  scopes: string[];
}

export interface ApiKeyCreateResponse {
  id: string;
  name: string;
  key: string;
  key_hint: string;
  scopes: string[];
  created_at: string;
}

/* ------------------------------------------------------------------ */
/*  Audit / Activity Log                                               */
/* ------------------------------------------------------------------ */

/** Audit-log entry returned by `GET /audit-log`. */
export interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  description: string;
  ip_address?: string;
  user_agent?: string;
  metadata?: Record<string, unknown>;
}

/** Paginated response wrapper for audit log queries. */
export interface AuditLogResponse {
  entries: AuditLogEntry[];
  total: number;
  has_more: boolean;
}

/** Known action types surfaced in the activity log. */
export type AuditAction =
  | "login"
  | "order_placed"
  | "order_cancelled"
  | "settings_changed"
  | "api_key_created"
  | "api_key_revoked"
  | "export_csv"
  | "password_changed"
  | "mfa_enabled"
  | "mfa_disabled";
