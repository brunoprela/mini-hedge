export type {
  InvestorInfo,
  CapitalAccountSummary,
  FundCapitalOverview,
  CapitalTransaction,
  ShareClassSummary,
  SubscriptionRequestSummary,
  RedemptionRequestSummary,
  SubscriptionState,
  RedemptionState,
  Position,
  PositionLot,
  PortfolioSummary,
  PortfolioInfo,
  FundDetail,
  FundPage,
  InvestorStatement,
  MonthlyPerformanceLetter,
  FundTermsSummary,
} from "@mini-hedge/api-types";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
