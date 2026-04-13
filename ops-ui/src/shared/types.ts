export type {
  AuditEntry,
  FundAccessGrant,
  FundDetail,
  OperatorInfo,
  UserInfo,
  // EOD
  EODRunSummary,
  EODRunResult,
  EODStepResult,
  EODStepName,
  EODStepStatus,
  // Reconciliation
  ReconSummary,
  TrackedBreak,
  BreakWithSLA,
  BreakStatus,
  BreakType,
  AgingSummary,
  AgingBucket,
  SLAStatus,
  // Cash
  CashBalance,
  SettlementRecord,
  SettlementLadder,
  SettlementLadderEntry,
  CashProjection,
  CashProjectionEntry,
  NettingResult,
  // Fees
  FeeScheduleResponse,
  FeeAccrualResponse,
  FeeScheduleUpdate,
  FeeType,
  AccrualStatus,
  // Portfolio
  PortfolioInfo,
  // Capital
  InvestorInfo,
  CapitalAccountSummary,
  FundCapitalOverview,
  ShareClassSummary,
  // Investor Operations
  SubscriptionRequestSummary,
  SubscriptionState,
  RedemptionRequestSummary,
  RedemptionState,
  FundTermsSummary,
  // Regulatory
  FormPFData,
  Filing13FReport,
  InvestorStatement,
  MonthlyPerformanceLetter,
} from "@mini-hedge/api-types";

/** Generic paginated response wrapper (UI-only — backend uses typed pages). */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** Customer info — matches backend CustomerInfo schema. Will move to api-types on next gen. */
export interface CustomerInfo {
  id: string;
  slug: string;
  name: string;
  customer_type: string;
  status: string;
}
