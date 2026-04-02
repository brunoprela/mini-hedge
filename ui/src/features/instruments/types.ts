/** Instrument data returned by the backend. */
export interface Instrument {
  id: string;
  ticker: string;
  name: string;
  asset_class: string;
  currency: string;
  exchange: string;
  country: string;
  sector: string | null;
  industry: string | null;
  is_active: boolean;
  listed_date: string | null;
}
