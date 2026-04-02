import { auth } from "@/shared/lib/auth";
import { redirect } from "next/navigation";
import { FundOverview } from "@/features/platform/components/fund-overview";

export default async function FundDashboardPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  const { fundSlug } = await params;

  return <FundOverview fundSlug={fundSlug} />;
}
