export type {
  AuditEntry,
  FundAccessGrant,
  FundDetail,
  OperatorInfo,
  UserInfo,
} from "@mini-hedge/api-types";

/** Generic paginated response wrapper (UI-only — backend uses typed pages). */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
