import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { InvestorDetailPageClient } from "./investor-detail-page-client";

export default async function InvestorDetailPage({
  params,
}: {
  params: Promise<{ fundSlug: string; investorId: string }>;
}) {
  const { fundSlug, investorId } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    {
      queryKey: ["investor-history", fundSlug, investorId],
      path: `/capital/investors/${investorId}/history`,
    },
    {
      queryKey: ["investor-transactions", fundSlug, investorId],
      path: `/capital/investors/${investorId}/transactions`,
    },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <InvestorDetailPageClient investorId={investorId} />
    </HydrationBoundary>
  );
}
