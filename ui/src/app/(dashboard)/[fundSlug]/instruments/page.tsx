import { HydrationBoundary } from "@tanstack/react-query";
import { InstrumentList } from "@/features/instruments/components/instrument-list";
import { prefetch } from "@/shared/lib/prefetch";

export default async function InstrumentsPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["instruments", fundSlug], path: "/instruments" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Instruments</h1>
        <InstrumentList />
      </div>
    </HydrationBoundary>
  );
}
