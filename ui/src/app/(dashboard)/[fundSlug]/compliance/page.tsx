import { HydrationBoundary } from "@tanstack/react-query";
import { prefetch } from "@/shared/lib/prefetch";
import { CompliancePageClient } from "./compliance-page-client";

export default async function CompliancePage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const { fundSlug } = await params;

  const { dehydratedState } = await prefetch(fundSlug, [
    { queryKey: ["portfolios", fundSlug], path: "/portfolios" },
    { queryKey: ["compliance-rules", fundSlug], path: "/compliance/rules" },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <CompliancePageClient />
    </HydrationBoundary>
  );
}
