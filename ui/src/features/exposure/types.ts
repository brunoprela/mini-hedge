export type { ExposureBreakdown, PortfolioExposure } from "@mini-hedge/api-types";

export interface ExposureHistoryEntry {
  date: string;
  long_value: string;
  short_value: string;
  net_value: string;
  gross_value: string;
}
