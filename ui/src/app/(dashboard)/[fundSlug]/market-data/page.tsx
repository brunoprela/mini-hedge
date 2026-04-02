import { PriceDashboard } from "@/features/market-data/components/price-dashboard";

export default function MarketDataPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Market Data</h1>
      <PriceDashboard />
    </div>
  );
}
