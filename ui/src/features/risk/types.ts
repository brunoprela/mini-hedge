export interface RiskSnapshot {
  id: string;
  portfolio_id: string;
  nav: string;
  var_95_1d: string;
  var_99_1d: string;
  expected_shortfall_95: string;
  max_drawdown: string;
  sharpe_ratio: string;
  snapshot_at: string;
}

export interface VaRContribution {
  instrument_id: string;
  weight: string;
  marginal_var: string;
  component_var: string;
  pct_contribution: string;
}

export interface VaRResult {
  portfolio_id: string;
  method: string;
  confidence_level: number;
  horizon_days: number;
  var_amount: string;
  var_pct: string;
  expected_shortfall: string;
  contributions: VaRContribution[];
  calculated_at: string;
}

export interface StressPositionImpact {
  instrument_id: string;
  current_value: string;
  stressed_value: string;
  pnl_impact: string;
  pct_change: string;
}

export interface StressTestResult {
  portfolio_id: string;
  scenario_name: string;
  scenario_type: string;
  total_pnl_impact: string;
  total_pct_change: string;
  position_impacts: StressPositionImpact[];
  calculated_at: string;
}

export interface FactorExposure {
  factor: string;
  exposure: string;
  contribution: string;
  pct_of_total: string;
}

export interface FactorDecomposition {
  portfolio_id: string;
  total_variance: string;
  systematic_variance: string;
  idiosyncratic_variance: string;
  systematic_pct: string;
  factor_exposures: FactorExposure[];
  calculated_at: string;
}
