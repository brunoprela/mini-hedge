export interface UserInfo {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
}

export interface OperatorInfo {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  platform_role: string | null;
}

export interface FundDetail {
  id: string;
  slug: string;
  name: string;
  status: string;
  base_currency: string;
}

export interface AuditEntry {
  id: string;
  event_id: string;
  event_type: string;
  actor_id: string | null;
  actor_type: string | null;
  fund_slug: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface FundAccessGrant {
  user_type: string;
  user_id: string;
  relation: string;
  relation_type: "role" | "permission";
  display_name: string | null;
}
