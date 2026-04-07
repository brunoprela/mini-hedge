export interface FeeSchedule {
  fund_slug: string;
  management_fee_bps: number;
  performance_fee_pct: string;
  hurdle_rate_pct: string;
  high_water_mark: boolean;
  crystallization_frequency: string;
  payment_frequency: string;
}

export interface FeeAccrual {
  id: string | null;
  portfolio_id: string;
  fee_type: "management" | "performance";
  accrual_date: string;
  nav_basis: string;
  accrued_amount: string;
  cumulative_amount: string;
  status: "pending" | "settled" | "reversed";
  created_at: string | null;
}
