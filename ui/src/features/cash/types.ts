export interface CashBalance {
  portfolio_id: string;
  currency: string;
  available_balance: string;
  pending_inflows: string;
  pending_outflows: string;
  total_balance: string;
  updated_at: string;
}

export interface SettlementRecord {
  id: string;
  portfolio_id: string;
  order_id: string | null;
  instrument_id: string;
  currency: string;
  settlement_amount: string;
  settlement_date: string;
  trade_date: string;
  status: string;
  created_at: string;
}

export interface SettlementLadderEntry {
  settlement_date: string;
  currency: string;
  expected_inflow: string;
  expected_outflow: string;
  net_flow: string;
  cumulative_balance: string;
}

export interface SettlementLadder {
  portfolio_id: string;
  entries: SettlementLadderEntry[];
  generated_at: string;
}

export interface CashProjectionEntry {
  projection_date: string;
  currency: string;
  opening_balance: string;
  inflows: string;
  outflows: string;
  closing_balance: string;
  flow_details: Record<string, string>[];
}

export interface CashProjection {
  portfolio_id: string;
  base_currency: string;
  horizon_days: number;
  entries: CashProjectionEntry[];
  projected_at: string;
}
