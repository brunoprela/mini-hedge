import { HydrationBoundary } from "@tanstack/react-query";
import { FundOverview } from "@/features/platform/components/fund-overview";
import { ActivityFeed } from "@/shared/components/activity-feed";
import { DashboardSummaryCards } from "@/shared/components/dashboard-summary-cards";
import { prefetch } from "@/shared/lib/prefetch";

export default async function FundDashboardPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["portfolios", fundSlug], path: "/portfolios" },
    { queryKey: ["me", "funds"], path: "/me/funds" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Main content column */}
        <div className="space-y-6">
          <FundOverview fundSlug={fundSlug} />
          <DashboardSummaryCards />
        </div>

        {/* Sidebar column — activity feed stays visible */}
        <div className="lg:sticky lg:top-6 lg:self-start">
          <ActivityFeed />
        </div>
      </div>
    </HydrationBoundary>
  );
}
