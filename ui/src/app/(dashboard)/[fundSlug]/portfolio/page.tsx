import { PortfolioList } from "@/features/portfolio/components/portfolio-list";

export default function PortfolioListPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Portfolios</h1>
      <PortfolioList />
    </div>
  );
}
