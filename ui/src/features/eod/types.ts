export type {
  EODRunResult,
  EODRunSummary,
  EODStepName,
  EODStepResult,
  EODStepStatus,
} from "@mini-hedge/api-types";

export interface NAVHistoryPoint {
  business_date: string;
  nav: string;
  nav_per_share: string;
}
