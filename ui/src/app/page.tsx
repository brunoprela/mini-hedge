import { redirect } from "next/navigation";
import { auth } from "@/shared/lib/auth";
import { serverFetch } from "@/shared/lib/api";
import type { FundInfo } from "@/features/platform/types";

export default async function RootPage() {
  const session = await auth();
  if (!session?.accessToken) redirect("/login");

  const funds = await serverFetch<FundInfo[]>(
    "/api/v1/me/funds",
    session.accessToken
  );

  if (funds.length === 0) {
    redirect("/unauthorized");
  }

  redirect(`/${funds[0].fund_slug}`);
}
