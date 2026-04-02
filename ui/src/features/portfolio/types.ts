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
