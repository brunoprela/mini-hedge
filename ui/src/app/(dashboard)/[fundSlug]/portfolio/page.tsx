import Link from "next/link";

const SEED_PORTFOLIOS = [
  { id: "20000000-0000-0000-0000-000000000001", name: "Equity Long/Short", strategy: "equity_long_short" },
  { id: "20000000-0000-0000-0000-000000000002", name: "Global Macro", strategy: "global_macro" },
];

export default async function PortfolioListPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Portfolios</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {SEED_PORTFOLIOS.map((p) => (
          <Link
            key={p.id}
            href={`/${fundSlug}/portfolio/${p.id}`}
            className="rounded-lg border border-[var(--border)] p-4 transition-colors hover:bg-[var(--muted)]"
          >
            <h3 className="font-medium">{p.name}</h3>
            <p className="text-sm text-[var(--muted-foreground)]">
              {p.strategy}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
