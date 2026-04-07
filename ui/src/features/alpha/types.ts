export type {
  OptimizationResult,
  OptimizationWeight,
  OrderIntent,
  ScenarioRun,
  WhatIfPosition,
  WhatIfResult,
} from "@mini-hedge/api-types";

/**
 * UI-only type for the what-if trade form. Not an API response model.
 * Maps to TradeInput on the backend but kept local since it's only
 * used as a request payload shape in the alpha feature.
 */
export interface HypotheticalTrade {
  instrument_id: string;
  side: string;
  quantity: string;
  price: string;
}
