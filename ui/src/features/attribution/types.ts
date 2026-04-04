export interface SectorAttribution {
  sector: string;
  portfolio_weight: string;
  benchmark_weight: string;
  portfolio_return: string;
  benchmark_return: string;
  allocation_effect: string;
  selection_effect: string;
  interaction_effect: string;
  total_effect: string;
}

export interface BrinsonFachlerResult {
  id: string | null;
  portfolio_id: string;
  period_start: string;
  period_end: string;
  portfolio_return: string;
  benchmark_return: string;
  active_return: string;
  total_allocation: string;
  total_selection: string;
  total_interaction: string;
  sectors: SectorAttribution[];
  calculated_at: string;
}

export interface RiskFactorAttribution {
  factor: string;
  factor_return: string;
  portfolio_exposure: string;
  pnl_contribution: string;
  pct_of_total: string;
}

export interface RiskBasedResult {
  id: string | null;
  portfolio_id: string;
  period_start: string;
  period_end: string;
  total_pnl: string;
  systematic_pnl: string;
  idiosyncratic_pnl: string;
  systematic_pct: string;
  factor_contributions: RiskFactorAttribution[];
  calculated_at: string;
}

export interface CumulativeAttribution {
  portfolio_id: string;
  period_start: string;
  period_end: string;
  cumulative_portfolio_return: string;
  cumulative_benchmark_return: string;
  cumulative_active_return: string;
  cumulative_allocation: string;
  cumulative_selection: string;
  cumulative_interaction: string;
  periods: BrinsonFachlerResult[];
  calculated_at: string;
}
