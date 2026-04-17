import { headers } from "next/headers";
import { redirect } from "next/navigation";
import createClient from "openapi-fetch";
import type { paths } from "@mini-hedge/api-types";
import type { FundInfo } from "@/features/platform/types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export default async function RootPage() {
  const headerStore = await headers();
  const accessToken = headerStore.get("x-auth-token");
  if (!accessToken) redirect("/login");

  // Server-side typed client: calls FastAPI directly with the bearer token
  // (the BFF proxy is not available in server components).
  const serverApi = createClient<paths>({ baseUrl: API_URL });
  const { data, error } = await serverApi.GET("/api/v1/me/funds", {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  if (error) throw error;
  const funds = (data ?? []) as unknown as FundInfo[];

  if (funds.length === 0) {
    redirect("/unauthorized");
  }

  redirect(`/${funds[0].fund_slug}`);
}
