export type {
  BrinsonFachlerResult,
  CumulativeAttribution,
  RiskBasedResult,
  RiskFactorAttribution,
  SectorAttribution,
} from "@mini-hedge/api-types";

export interface FXAttributionEntry {
  currency: string;
  local_return: string;
  fx_return: string;
  total_return: string;
  contribution: string;
  weight: string;
}

export interface FXAttributionResult {
  portfolio_id: string;
  start_date: string;
  end_date: string;
  total_fx_impact: string;
  entries: FXAttributionEntry[];
}
