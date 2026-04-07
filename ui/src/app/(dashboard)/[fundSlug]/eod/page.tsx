import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { EODPageClient } from "./eod-page-client";

export default async function EODPage({ params }: { params: Promise<{ fundSlug: string }> }) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, []);

  return (
    <HydrationBoundary state={dehydratedState}>
      <EODPageClient />
    </HydrationBoundary>
  );
}
