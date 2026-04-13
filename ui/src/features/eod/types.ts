export type {
  EODRunResult,
  EODRunSummary,
  EODStepName,
  EODStepResult,
  EODStepStatus,
} from "@mini-hedge/api-types";

export interface NAVHistoryPoint {
  business_date: string;
  nav: number;
  nav_per_share: number;
}
