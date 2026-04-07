import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { InvestorsPageClient } from "./investors-page-client";

export default async function InvestorsPage({ params }: { params: Promise<{ fundSlug: string }> }) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["investors", fundSlug], path: "/capital/investors" },
    { queryKey: ["capital-accounts", fundSlug], path: "/capital/accounts" },
    { queryKey: ["capital-overview", fundSlug], path: "/capital/overview" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <InvestorsPageClient />
    </HydrationBoundary>
  );
}
