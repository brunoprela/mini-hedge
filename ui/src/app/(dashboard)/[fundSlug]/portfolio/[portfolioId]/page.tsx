import { HydrationBoundary } from "@tanstack/react-query";
import { PortfolioDetailClient } from "./portfolio-detail-client";
import { prefetch } from "@/shared/lib/prefetch";

export default async function PortfolioDetailPage({
  params,
}: {
  params: Promise<{ fundSlug: string; portfolioId: string }>;
}) {
  const { fundSlug, portfolioId } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    {
      queryKey: ["positions", fundSlug, portfolioId],
      path: `/portfolios/${portfolioId}/positions`,
    },
    {
      queryKey: ["portfolio-summary", fundSlug, portfolioId],
      path: `/portfolios/${portfolioId}/summary`,
    },
    { queryKey: ["exposure", fundSlug, portfolioId], path: `/exposure/${portfolioId}` },
    { queryKey: ["risk-snapshot", fundSlug, portfolioId], path: `/risk/${portfolioId}/snapshot` },
    {
      queryKey: ["violations", fundSlug, portfolioId],
      path: `/compliance/violations?portfolio_id=${portfolioId}`,
    },
    {
      queryKey: ["orders", fundSlug, portfolioId],
      path: `/orders?portfolio_id=${portfolioId}`,
    },
    { queryKey: ["cash-balances", fundSlug, portfolioId], path: `/cash/${portfolioId}/balances` },
    {
      queryKey: ["fx-forwards", fundSlug, portfolioId],
      path: `/fx-hedging/forwards/${portfolioId}`,
    },
    {
      queryKey: ["fx-hedging-summary", fundSlug, portfolioId],
      path: `/fx-hedging/summary/${portfolioId}`,
    },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <PortfolioDetailClient portfolioId={portfolioId} />
    </HydrationBoundary>
  );
}
