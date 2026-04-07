import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { FeesPageClient } from "./fees-page-client";

export default async function FeesPage({ params }: { params: Promise<{ fundSlug: string }> }) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, []);

  return (
    <HydrationBoundary state={dehydratedState}>
      <FeesPageClient />
    </HydrationBoundary>
  );
}
