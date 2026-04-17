/**
 * Investor operations DTOs — re-exports from the generated api-types so the
 * UI stays in sync with backend Pydantic models. Aliases keep the shorter
 * local names while pointing at the authoritative generated shapes.
 */

import type { components } from "@mini-hedge/api-types";

type Schemas = components["schemas"];

export type SubscriptionState = Schemas["SubscriptionState"];
export type RedemptionState = Schemas["RedemptionState"];

export type SubscriptionRequest = Schemas["SubscriptionRequestSummary"];
export type RedemptionRequest = Schemas["RedemptionRequestSummary"];
export type FundTerms = Schemas["FundTermsSummary"];
export type QueueSummary = Schemas["QueueSummary"];
export type InvestorKYC = Schemas["InvestorKYCInfo"];
export type GateCheckResult = Schemas["GateCheckResult"];
export type GateAllocation = Schemas["GateAllocation"];
