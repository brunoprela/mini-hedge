export type ActionType = "DIVIDEND" | "STOCK_SPLIT" | "REVERSE_SPLIT" | "SPINOFF";

export type ProcessingStatus = "PENDING" | "PROCESSED" | "FAILED" | "SKIPPED";

export interface PositionAdjustment {
  quantity_delta: number;
  cost_basis_adjustment: number;
  cash_amount: number;
}

export interface ProcessedAction {
  id: string;
  action_id: string;
  instrument_id: string;
  action_type: ActionType;
  ex_date: string;
  record_date: string;
  pay_date: string;
  status: ProcessingStatus;
  description: string;
  adjustments: PositionAdjustment[];
  processed_at: string;
  created_at: string;
}
