import { HydrationBoundary } from "@tanstack/react-query";
import { PriceDashboard } from "@/features/market-data/components/price-dashboard";
import { prefetch } from "@/shared/lib/prefetch";

export default async function MarketDataPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["instruments", fundSlug], path: "/instruments" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Market Data</h1>
        <PriceDashboard />
      </div>
    </HydrationBoundary>
  );
}
