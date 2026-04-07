import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { TCAOrderDetailClient } from "./tca-order-detail-client";

export default async function TCAPage({
  params,
}: {
  params: Promise<{ fundSlug: string; orderId: string }>;
}) {
  const { fundSlug, orderId } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["order-tca", fundSlug, orderId], path: `/orders/${orderId}/tca` },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <TCAOrderDetailClient orderId={orderId} />
    </HydrationBoundary>
  );
}
