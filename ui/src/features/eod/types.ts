export type { EODRunResult, EODRunSummary } from "@mini-hedge/api-types";

export interface EODStepResult {
  step: string;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  details: Record<string, unknown> | null;
}
