/** Investor operations DTOs — matches backend Pydantic models. */

export type SubscriptionState =
  | "draft"
  | "pending_kyc"
  | "kyc_approved"
  | "kyc_rejected"
  | "pending_ops_review"
  | "pending_gp_approval"
  | "approved"
  | "rejected"
  | "pending_wire"
  | "wire_confirmed"
  | "queued_for_nav"
  | "executed"
  | "cancelled";

export type RedemptionState =
  | "draft"
  | "pending_validation"
  | "validated"
  | "validation_failed"
  | "pending_gate_check"
  | "gate_applied"
  | "queued_for_nav"
  | "nav_calculated"
  | "pending_payment"
  | "payment_sent"
  | "executed"
  | "cancelled";

export interface SubscriptionRequest {
  id: string;
  investor_id: string;
  share_class: string;
  requested_amount: string;
  state: SubscriptionState;
  submitted_at: string;
  kyc_decision_at: string | null;
  kyc_decision_by: string | null;
  ops_decision_at: string | null;
  ops_decision_by: string | null;
  gp_decision_at: string | null;
  gp_decision_by: string | null;
  wire_confirmed_at: string | null;
  wire_reference: string | null;
  dealing_date: string | null;
  executed_at: string | null;
  nav_per_share: string | null;
  shares_issued: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
}

export interface RedemptionRequest {
  id: string;
  investor_id: string;
  requested_amount: string;
  approved_amount: string | null;
  state: RedemptionState;
  submitted_at: string;
  notice_date: string;
  earliest_redemption_date: string | null;
  lock_up_expiry_date: string | null;
  gate_applied: boolean;
  gate_pct: string | null;
  dealing_date: string | null;
  nav_per_share: string | null;
  shares_redeemed: string | null;
  payment_due_date: string | null;
  payment_sent_at: string | null;
  payment_reference: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
}

export interface FundTerms {
  id: string;
  share_class: string;
  lock_up_months: number;
  notice_period_days: number;
  redemption_frequency: string;
  gate_pct: string;
  minimum_subscription: string;
  minimum_redemption: string;
  dealing_day: number;
  payment_days: number;
  is_active: boolean;
}

export interface QueueSummary {
  pending_subscriptions: number;
  pending_redemptions: number;
  total_subscription_amount: string;
  total_redemption_amount: string;
  next_dealing_date: string | null;
}

export interface InvestorKYC {
  investor_id: string;
  kyc_status: string;
  aml_status: string;
  sanctions_clear: boolean;
  pep_flag: boolean;
  source_of_funds_verified: boolean;
  accredited_investor: boolean;
  last_screened_at: string | null;
  screening_expires_at: string | null;
  screening_provider: string | null;
}

export interface GateCheckResult {
  gate_triggered: boolean;
  total_requested: string;
  total_approved: string;
  gate_capacity: string;
  allocations: GateAllocation[];
}

export interface GateAllocation {
  request_id: string;
  original_amount: string;
  approved_amount: string;
  proration_pct: string;
}
