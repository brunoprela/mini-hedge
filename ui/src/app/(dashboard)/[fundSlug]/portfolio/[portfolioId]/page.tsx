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
      <h1 className="text-2xl font-semibold">Positions</h1>
      <PortfolioSummary portfolioId={portfolioId} />
      <PositionTable portfolioId={portfolioId} />
    </div>
  );
}
