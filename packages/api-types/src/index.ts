/**
 * @mini-hedge/api-types — auto-generated from FastAPI OpenAPI schema.
 *
 * DO NOT EDIT MANUALLY. Run `make gen-types` to regenerate.
 *
 * Usage:
 *   import type { OrderSummary, AlgoType } from "@mini-hedge/api-types";
 *
 * For full path/operation types:
 *   import type { paths, operations } from "@mini-hedge/api-types";
 */
export type { components, paths, operations } from "../generated/openapi.js";

// ─── Convenience aliases ────────────────────────────────────────────
// Saves consumers from writing components["schemas"]["..."] everywhere.

import type { components } from "../generated/openapi.js";

type Schemas = components["schemas"];

// Platform
export type FundDetail = Schemas["FundDetail"];
export type FundInfo = Schemas["FundInfo"];
export type PortfolioInfo = Schemas["PortfolioInfo"];
export type UserInfo = Schemas["UserInfo"];
export type OperatorInfo = Schemas["OperatorInfo"];
export type AuditEntry = Schemas["AuditEntry"];
export type AuditPage = Schemas["AuditPage"];
export type FundAccessGrant = Schemas["FundAccessGrant"];
export type FundPage = Schemas["FundPage"];
export type UserPage = Schemas["UserPage"];
export type OperatorPage = Schemas["OperatorPage"];

// Orders
export type OrderSummary = Schemas["OrderSummary"];
export type CreateOrderRequest = Schemas["CreateOrderRequest"];
export type CreateAlgoOrderRequest = Schemas["CreateAlgoOrderRequest"];
export type FillDetail = Schemas["FillDetail"];
export type AlgoType = Schemas["AlgoType"];
export type AlgoParams = Schemas["AlgoParams"];
export type OrderSide = Schemas["OrderSide"];
export type OrderType = Schemas["OrderType"];
export type OrderState = Schemas["OrderState"];
export type TimeInForce = Schemas["TimeInForce"];

// Allocations
export type BlockAllocationSummary = Schemas["BlockAllocationSummary"];
export type AllocationLegSummary = Schemas["AllocationLegSummary"];
export type AllocationLegRequest = Schemas["AllocationLegRequest"];
export type CreateBlockAllocationRequest = Schemas["CreateBlockAllocationRequest"];
export type AllocationState = Schemas["AllocationState"];

// Instruments & Market Data
export type Instrument = Schemas["Instrument"];
export type PriceSnapshot = Schemas["PriceSnapshot"];
export type FXRateSnapshot = Schemas["FXRateSnapshot"];

// Positions & Portfolio
export type Position = Schemas["Position"];
export type PositionLot = Schemas["PositionLot"];
export type PortfolioSummary = Schemas["PortfolioSummary"];
export type TradeRequest = Schemas["TradeRequest"];

// Compliance
export type RuleDefinition = Schemas["RuleDefinition"];
export type Violation = Schemas["Violation"];
export type ComplianceDecision = Schemas["ComplianceDecision"];

// Exposure
export type PortfolioExposure = Schemas["PortfolioExposure"];
export type ExposureBreakdown = Schemas["ExposureBreakdown"];
export type ExposureSnapshot = Schemas["ExposureSnapshot"];

// Risk
export type RiskSnapshot = Schemas["RiskSnapshot"];
export type VaRContribution = Schemas["VaRContribution"];
export type VaRResult = Schemas["VaRResult"];
export type StressPositionImpact = Schemas["StressPositionImpact"];
export type StressTestResult = Schemas["StressTestResult"];
export type FactorExposure =
  Schemas["app__modules__risk_engine__interfaces__factor__FactorExposure"];
export type QuantFactorExposure =
  Schemas["app__modules__quant_research__interfaces__quant__FactorExposure"];
export type FactorDecomposition = Schemas["FactorDecomposition"];

// Cash
export type CashBalance = Schemas["CashBalance"];
export type SettlementRecord = Schemas["SettlementRecord"];
export type SettlementLadderEntry = Schemas["SettlementLadderEntry"];
export type SettlementLadder = Schemas["SettlementLadder"];
export type CashProjectionEntry = Schemas["CashProjectionEntry"];
export type CashProjection = Schemas["CashProjection"];

// Capital Accounts
export type CapitalAccountSummary = Schemas["CapitalAccountSummary"];
export type InvestorInfo = Schemas["InvestorInfo"];
export type FundCapitalOverview = Schemas["FundCapitalOverview"];
export type CapitalTransaction = Schemas["CapitalTransaction"];

// Alpha / What-If
export type WhatIfPosition = Schemas["WhatIfPosition"];
export type WhatIfResult = Schemas["WhatIfResult"];
export type OptimizationWeight = Schemas["OptimizationWeight"];
export type OrderIntent = Schemas["OrderIntent"];
export type OptimizationResult = Schemas["OptimizationResult"];
export type ScenarioRun = Schemas["ScenarioRun"];

// Attribution
export type InstrumentAttribution = Schemas["InstrumentAttribution"];
export type SectorAttribution = Schemas["SectorAttribution"];
export type BrinsonFachlerResult = Schemas["BrinsonFachlerResult"];
export type RiskFactorAttribution = Schemas["RiskFactorAttribution"];
export type RiskBasedResult = Schemas["RiskBasedResult"];
export type CumulativeAttribution = Schemas["CumulativeAttribution"];

// EOD
export type EODRunSummary = Schemas["EODRunSummary"];
export type EODRunResult = Schemas["EODRunResult"];
export type EODStepResult = Schemas["EODStepResult"];
export type EODStepName = Schemas["EODStepName"];
export type EODStepStatus = Schemas["EODStepStatus"];

// FX Hedging
export type FXForwardContract = Schemas["FXForwardContract"];
export type FXForwardCreate = Schemas["FXForwardCreate"];
export type FXForwardClose = Schemas["FXForwardClose"];
export type FXForwardRoll = Schemas["FXForwardRoll"];
export type FXForwardDirection = Schemas["FXForwardDirection"];
export type FXForwardStatus = Schemas["FXForwardStatus"];
export type FXHedgingSummary = Schemas["FXHedgingSummary"];
export type FXInterestRate = Schemas["FXInterestRate"];
export type HedgeRecommendationResponse = Schemas["HedgeRecommendationResponse"];
export type FXAttributionResult = Schemas["FXAttributionResult"];

// Fees
export type FeeScheduleResponse = Schemas["FeeScheduleResponse"];
export type FeeAccrualResponse = Schemas["FeeAccrualResponse"];
export type FeeScheduleUpdate = Schemas["FeeScheduleUpdate"];
export type FeeType = Schemas["FeeType"];
export type AccrualStatus = Schemas["AccrualStatus"];

// Reconciliation
export type ReconSummary = Schemas["ReconSummary"];
export type TrackedBreak = Schemas["TrackedBreak"];
export type BreakWithSLA = Schemas["BreakWithSLA"];
export type BreakStatus = Schemas["BreakStatus"];
export type BreakType = Schemas["BreakType"];
export type AgingSummary = Schemas["AgingSummary"];
export type AgingBucket = Schemas["AgingBucket"];
export type SLAStatus = Schemas["SLAStatus"];

// Investor Operations
export type SubscriptionRequestSummary = Schemas["SubscriptionRequestSummary"];
export type SubscriptionState = Schemas["SubscriptionState"];
export type RedemptionRequestSummary = Schemas["RedemptionRequestSummary"];
export type RedemptionState = Schemas["RedemptionState"];
export type FundTermsSummary = Schemas["FundTermsSummary"];

// Regulatory
export type FormPFData = Schemas["FormPFData"];
export type Filing13FReport = Schemas["Filing13FReport"];
export type InvestorStatement = Schemas["InvestorStatement"];
export type MonthlyPerformanceLetter = Schemas["MonthlyPerformanceLetter"];

// Cash (extra)
export type NettingResult = Schemas["NettingResult"];
export type ShareClassSummary = Schemas["ShareClassSummary"];

// Multi-Broker & TCA
export type BrokerScorecard = Schemas["BrokerScorecard"];
export type BestExecutionReport = Schemas["BestExecutionReport"];
export type TCAReport = Schemas["TCAReport"];
export type PortfolioTCAReport = Schemas["PortfolioTCAReport"];
export type FundTCASummary = Schemas["FundTCASummary"];
