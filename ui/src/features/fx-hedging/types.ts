/**
 * FX hedging types — re-exported from auto-generated API types.
 *
 * Only add UI-only types here (not returned by the API).
 */
export type {
  FXAttributionResult,
  FXForwardClose,
  FXForwardContract,
  FXForwardCreate,
  FXForwardDirection,
  FXForwardRoll,
  FXForwardStatus,
  FXHedgingSummary,
  FXInterestRate,
  HedgeRecommendationResponse,
} from "@mini-hedge/api-types";

/** UI-only: hedge recommendation row from the recommendations endpoint. */
export interface HedgeRecommendation {
  currency_pair: string;
  base_currency: string;
  quote_currency: string;
  notional: string;
  direction: string;
  hedge_ratio: string;
  tenor_days: number;
  estimated_forward: string;
  estimated_cost_bps: string;
}

/** UI-only: roll recommendation row. */
export interface RollRecommendation {
  forward_id: string;
  currency_pair: string;
  days_to_expiry: number;
  current_notional: string;
  estimated_roll_cost_bps: string;
  recommended_tenor_days: number;
}
