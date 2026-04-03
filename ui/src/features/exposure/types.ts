export interface PortfolioExposure {
  portfolio_id: string;
  gross_exposure: string;
  net_exposure: string;
  long_exposure: string;
  short_exposure: string;
  long_count: number;
  short_count: number;
  calculated_at: string;
  breakdowns: Record<string, ExposureBreakdown[]>;
}

export interface ExposureBreakdown {
  dimension: string;
  key: string;
  long_value: string;
  short_value: string;
  net_value: string;
  gross_value: string;
  weight_pct: string;
}
