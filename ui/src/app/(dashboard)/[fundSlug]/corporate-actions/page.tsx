import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { CorporateActionsPageClient } from "./corporate-actions-page-client";

export default async function CorporateActionsPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["corporate-actions", fundSlug], path: "/corporate-actions" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <CorporateActionsPageClient />
    </HydrationBoundary>
  );
}
