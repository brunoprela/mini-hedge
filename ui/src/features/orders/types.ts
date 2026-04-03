export interface OrderSummary {
  id: string;
  portfolio_id: string;
  instrument_id: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  quantity: string;
  filled_quantity: string;
  limit_price: string | null;
  avg_fill_price: string | null;
  state: string;
  rejection_reason: string | null;
  compliance_results: Record<string, unknown>[] | null;
  time_in_force: string;
  created_at: string;
  updated_at: string;
}

export interface CreateOrderRequest {
  portfolio_id: string;
  instrument_id: string;
  side: "buy" | "sell";
  order_type?: "market" | "limit";
  quantity: string;
  limit_price?: string;
  time_in_force?: "day" | "gtc" | "ioc";
}

export interface FillDetail {
  id: string;
  order_id: string;
  quantity: string;
  price: string;
  filled_at: string;
}
