export interface HypotheticalTrade {
  instrument_id: string;
  side: string;
  quantity: string;
  price: string;
}

export interface WhatIfPosition {
  instrument_id: string;
  current_quantity: string;
  proposed_quantity: string;
  current_value: string;
  proposed_value: string;
  current_weight: string;
  proposed_weight: string;
}

export interface WhatIfResult {
  portfolio_id: string;
  scenario_name: string;
  current_nav: string;
  proposed_nav: string;
  nav_change: string;
  nav_change_pct: string;
  current_var_95: string | null;
  proposed_var_95: string | null;
  positions: WhatIfPosition[];
  compliance_issues: string[];
  calculated_at: string;
}

export interface OptimizationWeight {
  instrument_id: string;
  current_weight: string;
  target_weight: string;
  delta_weight: string;
  delta_shares: string;
  delta_value: string;
}

export interface OrderIntent {
  instrument_id: string;
  side: string;
  quantity: string;
  estimated_value: string;
  reason: string;
}

export interface OptimizationResult {
  id: string | null;
  portfolio_id: string;
  objective: string;
  expected_return: string;
  expected_risk: string;
  sharpe_ratio: string | null;
  weights: OptimizationWeight[];
  order_intents: OrderIntent[];
  calculated_at: string;
}

export interface ScenarioRun {
  id: string;
  portfolio_id: string;
  scenario_name: string;
  trades: Record<string, string>[];
  result_summary: Record<string, string>;
  status: string;
  created_at: string;
}
