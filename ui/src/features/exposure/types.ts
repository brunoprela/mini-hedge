export type { ExposureBreakdown, PortfolioExposure } from "@mini-hedge/api-types";

export interface DrilldownItem {
  instrument_id: string;
  long_value: string;
  short_value: string;
  net_value: string;
  gross_value: string;
  weight_pct: string;
}

export interface DimensionDrilldown {
  dimension: string;
  key: string;
  items: DrilldownItem[];
}

export interface ExposureHistoryEntry {
  date: string;
  long_value: string;
  short_value: string;
  net_value: string;
  gross_value: string;
}
