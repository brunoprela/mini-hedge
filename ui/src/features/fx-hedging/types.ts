/** FX hedging types — inline until api-types regeneration. */

export type FXForwardStatus = "open" | "closed" | "rolled" | "expired" | "settled";
export type FXForwardDirection = "buy" | "sell";

export interface FXForwardContract {
  id: string;
  portfolio_id: string;
  base_currency: string;
  quote_currency: string;
  direction: FXForwardDirection;
  notional: string;
  contract_rate: string;
  spot_at_inception: string;
  trade_date: string;
  maturity_date: string;
  status: FXForwardStatus;
  counterparty: string | null;
  roll_from_id: string | null;
  close_rate: string | null;
  close_spot: string | null;
  realized_pnl: string | null;
  mtm_value: string | null;
  mtm_timestamp: string | null;
}

export interface FXForwardCreate {
  portfolio_id: string;
  base_currency: string;
  quote_currency: string;
  direction: FXForwardDirection;
  notional: string;
  tenor_days: number;
  counterparty?: string;
}

export interface FXForwardClose {
  forward_id: string;
}

export interface FXForwardRoll {
  forward_id: string;
  new_tenor_days: number;
}

export interface FXHedgingSummary {
  portfolio_id: string;
  total_open_forwards: number;
  total_notional: string;
  net_mtm: string;
  currencies_hedged: string[];
  last_mtm_timestamp: string | null;
}

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

export interface FXInterestRate {
  currency: string;
  rate: string;
  tenor_days: number;
  source: string | null;
  updated_at: string;
}

export interface RollRecommendation {
  forward_id: string;
  currency_pair: string;
  days_to_expiry: number;
  current_notional: string;
  estimated_roll_cost_bps: string;
  recommended_tenor_days: number;
}
