import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { ExposurePageClient } from "./exposure-page-client";

export default async function ExposurePage({ params }: { params: Promise<{ fundSlug: string }> }) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["portfolios", fundSlug], path: "/portfolios" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <ExposurePageClient />
    </HydrationBoundary>
  );
}
