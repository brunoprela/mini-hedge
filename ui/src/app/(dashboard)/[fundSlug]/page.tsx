import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { DashboardHome } from "./dashboard-home";

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
      <DashboardHome />
    </HydrationBoundary>
  );
}
