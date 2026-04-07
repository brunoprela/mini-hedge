export interface TCAReport {
  order_id: string;
  instrument_id: string;
  side: string;
  quantity: string;
  arrival_price: string;
  avg_fill_price: string;
  vwap: string;
  participation_rate_pct: string;
  execution_duration_seconds: string;
  commission_bps: string;
  spread_cost_bps: string;
  timing_cost_bps: string;
  impact_cost_bps: string;
  opportunity_cost_bps: string;
  total_cost_bps: string;
  total_cost_usd: string;
  computed_at: string;
}

export interface PortfolioTCAReport {
  portfolio_id: string;
  total_orders: number;
  avg_total_cost_bps: string;
  avg_commission_bps: string;
  avg_spread_cost_bps: string;
  avg_impact_cost_bps: string;
  total_cost_usd: string;
  reports: TCAReport[];
}

export interface FundTCASummary {
  period_start: string;
  period_end: string;
  total_orders: number;
  avg_total_cost_bps: string;
  avg_commission_bps: string;
  avg_spread_cost_bps: string;
  avg_timing_cost_bps: string;
  avg_impact_cost_bps: string;
  total_cost_usd: string;
}
