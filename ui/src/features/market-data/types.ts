/** Price snapshot returned by the backend. */
export interface PriceSnapshot {
  instrument_id: string;
  bid: string;
  ask: string;
  mid: string;
  volume: string | null;
  timestamp: string;
  source: string;
}
