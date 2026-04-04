import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { RiskPageClient } from "./risk-page-client";

export default async function RiskPage({ params }: { params: Promise<{ fundSlug: string }> }) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["portfolios", fundSlug], path: "/portfolios" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <RiskPageClient />
    </HydrationBoundary>
  );
}
