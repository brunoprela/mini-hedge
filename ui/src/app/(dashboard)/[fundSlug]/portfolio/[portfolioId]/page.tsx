import { ComplianceBanner } from "@/features/compliance/components/compliance-banner";
import { ExposureSummary } from "@/features/exposure/components/exposure-summary";
import { OrderBlotter } from "@/features/orders/components/order-blotter";
import { PortfolioSummary } from "@/features/portfolio/components/portfolio-summary";
import { PositionTable } from "@/features/portfolio/components/position-table";

export default async function PortfolioDetailPage({
  params,
}: {
  params: Promise<{ fundSlug: string; portfolioId: string }>;
}) {
  const { portfolioId } = await params;

  return (
    <div className="space-y-4">
      <ComplianceBanner portfolioId={portfolioId} />

      <h1 className="text-2xl font-semibold">Portfolio</h1>
      <PortfolioSummary portfolioId={portfolioId} />

      <h2 className="text-lg font-semibold">Exposure</h2>
      <ExposureSummary portfolioId={portfolioId} />

      <h2 className="text-lg font-semibold">Positions</h2>
      <PositionTable portfolioId={portfolioId} />

      <h2 className="text-lg font-semibold">Orders</h2>
      <OrderBlotter portfolioId={portfolioId} />
    </div>
  );
}
