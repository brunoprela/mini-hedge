import { dehydrate, QueryClient } from "@tanstack/react-query";
import { headers } from "next/headers";
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@mini-hedge/api-types";

/**
 * Create a server-side QueryClient, prefetch multiple queries in parallel,
 * and return the dehydrated state for HydrationBoundary.
 *
 * Reads the access token from the x-auth-token header injected by middleware,
 * avoiding a redundant auth() call (which decrypts the JWT again).
 *
 * Uses `openapi-fetch` (same typed client as client-side) targeted at the
 * upstream FastAPI directly — the `/api/proxy` BFF isn't reachable from Next
 * server components. Auth headers are attached via a per-request middleware.
 */

interface PrefetchEntry {
  queryKey: readonly unknown[];
  /** Route under `/api/v1` (e.g. `/portfolios`, `/capital/investors`). */
  path: string;
}

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function prefetch(fundSlug: string, entries: PrefetchEntry[]) {
  const headerStore = await headers();
  const accessToken = headerStore.get("x-auth-token");
  if (!accessToken) {
    return { dehydratedState: dehydrate(new QueryClient()) };
  }

  const authMiddleware: Middleware = {
    async onRequest({ request }) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
      request.headers.set("X-Fund-Slug", fundSlug);
      return request;
    },
  };

  const serverApi = createClient<paths>({ baseUrl: API_URL });
  serverApi.use(authMiddleware);

  const queryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000 } },
  });

  await Promise.allSettled(
    entries.map((entry) =>
      queryClient.prefetchQuery({
        queryKey: entry.queryKey,
        queryFn: async () => {
          // Cast: `entry.path` is an arbitrary string (from call-site),
          // narrowed to the openapi `paths` map at runtime.
          // openapi-fetch is strictly typed by the `paths` map, but we accept
          // arbitrary string paths for backward compat. Cast via `any` to
          // bypass the strict `PathsWithMethod` constraint.
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const call = serverApi.GET as (p: string, opts: unknown) => Promise<{ data?: unknown; error?: unknown }>;
          const { data, error } = await call(`/api/v1${entry.path}`, {
            cache: "no-store",
          });
          if (error) throw error;
          return data;
        },
      }),
    ),
  );

  return { dehydratedState: dehydrate(queryClient) };
}
