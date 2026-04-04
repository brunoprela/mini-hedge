import { HydrationBoundary } from "@tanstack/react-query";
import { PortfolioList } from "@/features/portfolio/components/portfolio-list";
import { prefetch } from "@/shared/lib/prefetch";

export default async function PortfolioListPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["portfolios", fundSlug], path: "/portfolios" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Portfolios</h1>
        <PortfolioList />
      </div>
    </HydrationBoundary>
  );
}
