import { redirect } from "next/navigation";
import { FundOverview } from "@/features/platform/components/fund-overview";
import { ActivityFeed } from "@/shared/components/activity-feed";
import { auth } from "@/shared/lib/auth";

export default async function FundDashboardPage({
  params,
}: {
  params: Promise<{ fundSlug: string }>;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  const { fundSlug } = await params;

  return (
    <div className="space-y-6">
      <FundOverview fundSlug={fundSlug} />
      <ActivityFeed />
    </div>
  );
}
