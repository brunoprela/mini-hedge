import { HydrationBoundary } from "@tanstack/react-query";
import { AttributionSummaryCard } from "@/features/attribution/components/attribution-summary-card";
import { CashSummaryCard } from "@/features/cash/components/cash-summary-card";
import { ComplianceBanner } from "@/features/compliance/components/compliance-banner";
import { ExposureSummary } from "@/features/exposure/components/exposure-summary";
import { OrderBlotter } from "@/features/orders/components/order-blotter";
import { PortfolioSummary } from "@/features/portfolio/components/portfolio-summary";
import { PositionTable } from "@/features/portfolio/components/position-table";
import { RiskSummaryCard } from "@/features/risk/components/risk-summary-card";
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
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <div className="space-y-4">
        <ComplianceBanner portfolioId={portfolioId} />

        <h1 className="text-2xl font-semibold">Portfolio</h1>
        <PortfolioSummary portfolioId={portfolioId} />

        <h2 className="text-lg font-semibold">Exposure</h2>
        <ExposureSummary portfolioId={portfolioId} />

        <h2 className="text-lg font-semibold">Risk</h2>
        <RiskSummaryCard portfolioId={portfolioId} />

        <h2 className="text-lg font-semibold">Positions</h2>
        <PositionTable portfolioId={portfolioId} />

        <h2 className="text-lg font-semibold">Orders</h2>
        <OrderBlotter portfolioId={portfolioId} />

        <h2 className="text-lg font-semibold">Cash</h2>
        <CashSummaryCard portfolioId={portfolioId} />

        <h2 className="text-lg font-semibold">Attribution</h2>
        <AttributionSummaryCard portfolioId={portfolioId} />
      </div>
    </HydrationBoundary>
  );
}
