import { HydrationBoundary } from "@tanstack/react-query";
import { redirect } from "next/navigation";
import { FundOverview } from "@/features/platform/components/fund-overview";
import { ActivityFeed } from "@/shared/components/activity-feed";
import { DashboardSummaryCards } from "@/shared/components/dashboard-summary-cards";
import { auth } from "@/shared/lib/auth";
import { prefetch } from "@/shared/lib/prefetch";

export default async function FundDashboardPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["portfolios", fundSlug], path: "/portfolios" },
    { queryKey: ["me", "funds"], path: "/me/funds" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <div className="space-y-6">
        <FundOverview fundSlug={fundSlug} />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <DashboardSummaryCards />
          </div>
          <div>
            <ActivityFeed />
          </div>
        </div>
      </div>
    </HydrationBoundary>
  );
}
