import { dehydrate, QueryClient } from "@tanstack/react-query";
import { headers } from "next/headers";
import { serverFetch } from "./api";

/**
 * Create a server-side QueryClient, prefetch multiple queries in parallel,
 * and return the dehydrated state for HydrationBoundary.
 *
 * Reads the access token from the x-auth-token header injected by middleware,
 * avoiding a redundant auth() call (which decrypts the JWT again).
 */

interface PrefetchEntry {
  queryKey: readonly unknown[];
  path: string;
}

export async function prefetch(fundSlug: string, entries: PrefetchEntry[]) {
  const headerStore = await headers();
  const accessToken = headerStore.get("x-auth-token");
  if (!accessToken) {
    return { dehydratedState: dehydrate(new QueryClient()) };
  }

  const queryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000 } },
  });

  await Promise.allSettled(
    entries.map((entry) =>
      queryClient.prefetchQuery({
        queryKey: entry.queryKey,
        queryFn: () => serverFetch(`/api/v1${entry.path}`, accessToken, { fundSlug }),
      }),
    ),
  );

  return { dehydratedState: dehydrate(queryClient) };
}
