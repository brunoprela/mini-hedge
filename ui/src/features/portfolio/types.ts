/** Position data returned by the backend. */
export interface Position {
  instrument_id: string;
  quantity: string;
  avg_cost: string;
  cost_basis: string;
  realized_pnl: string;
  market_price: string;
  market_value: string;
  unrealized_pnl: string;
  currency: string;
  last_updated: string;
}

export interface PositionLot {
  id: string;
  portfolio_id: string;
  instrument_id: string;
  quantity: string;
  original_quantity: string;
  price: string;
  acquired_at: string;
  trade_id: string;
}

export interface PortfolioSummary {
  portfolio_id: string;
  total_market_value: string;
  total_cost_basis: string;
  total_realized_pnl: string;
  total_unrealized_pnl: string;
  position_count: number;
}

export interface PortfolioInfo {
  id: string;
  slug: string;
  name: string;
  strategy: string | null;
  fund_id: string;
}

export interface TradeRequest {
  portfolio_id: string;
  instrument_id: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  currency?: string;
}
