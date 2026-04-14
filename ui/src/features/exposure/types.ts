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
  id: string;
  portfolio_id: string;
  fund_slug: string;
  long_exposure: string;
  short_exposure: string;
  net_exposure: string;
  gross_exposure: string;
  long_count: number;
  short_count: number;
  snapshot_at: string;
}
