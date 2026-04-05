import { headers } from "next/headers";
import { redirect } from "next/navigation";
import type { FundInfo } from "@/features/platform/types";
import { serverFetch } from "@/shared/lib/api";

export default async function RootPage() {
  const headerStore = await headers();
  const accessToken = headerStore.get("x-auth-token");
  if (!accessToken) redirect("/login");

  const funds = await serverFetch<FundInfo[]>("/api/v1/me/funds", accessToken);

  if (funds.length === 0) {
    redirect("/unauthorized");
  }

  redirect(`/${funds[0].fund_slug}`);
}
