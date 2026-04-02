/** Instrument data returned by the backend. */
export interface Instrument {
  id: string;
  ticker: string;
  name: string;
  asset_class: string;
  currency: string;
  exchange: string | null;
  country: string | null;
  sector: string | null;
  is_active: boolean;
}
