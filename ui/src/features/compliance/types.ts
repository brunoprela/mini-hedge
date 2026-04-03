export interface Violation {
  id: string;
  portfolio_id: string;
  rule_id: string;
  rule_name: string;
  severity: "block" | "warning" | "breach";
  message: string;
  current_value: string | null;
  limit_value: string | null;
  detected_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
}
