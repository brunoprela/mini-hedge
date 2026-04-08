import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { OperationsPageClient } from "./operations-page-client";

export default async function OperationsPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["subscriptions", fundSlug, "all"], path: "/investor-operations/subscriptions" },
    { queryKey: ["redemptions", fundSlug, "all"], path: "/investor-operations/redemptions" },
    { queryKey: ["investor-ops-queue", fundSlug], path: "/investor-operations/queue" },
    { queryKey: ["investors", fundSlug], path: "/capital/investors" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <OperationsPageClient />
    </HydrationBoundary>
  );
}
