import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { AlphaPageClient } from "./alpha-page-client";

export default async function AlphaPage({ params }: { params: Promise<{ fundSlug: string }> }) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["portfolios", fundSlug], path: "/portfolios" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <AlphaPageClient />
    </HydrationBoundary>
  );
}
