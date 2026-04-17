/**
 * TCA DTOs — re-exports from generated api-types so the UI stays in sync
 * with backend Pydantic models.
 */

import type { components } from "@mini-hedge/api-types";

type Schemas = components["schemas"];

export type TCAReport = Schemas["TCAReport"];
export type PortfolioTCAReport = Schemas["PortfolioTCAReport"];
export type FundTCASummary = Schemas["FundTCASummary"];
