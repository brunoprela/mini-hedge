import { dehydrate, QueryClient } from "@tanstack/react-query";
import { auth } from "@/shared/lib/auth";
import { serverFetch } from "./api";

/**
 * Create a server-side QueryClient, prefetch multiple queries in parallel,
 * and return the dehydrated state for HydrationBoundary.
 *
 * Usage in server components:
 * ```ts
 * const { dehydratedState } = await prefetch(fundSlug, [
 *   { queryKey: ["positions", fundSlug, pid], path: `/portfolios/${pid}/positions` },
 *   { queryKey: ["orders", fundSlug, pid], path: `/orders?portfolio_id=${pid}` },
 * ]);
 * ```
 */

interface PrefetchEntry {
  queryKey: readonly unknown[];
  path: string;
}

export async function prefetch(fundSlug: string, entries: PrefetchEntry[]) {
  const session = await auth();
  if (!session?.accessToken) {
    return { dehydratedState: dehydrate(new QueryClient()) };
  }

  const queryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000 } },
  });

  await Promise.allSettled(
    entries.map((entry) =>
      queryClient.prefetchQuery({
        queryKey: entry.queryKey,
        queryFn: () => serverFetch(`/api/v1${entry.path}`, session.accessToken, { fundSlug }),
      }),
    ),
  );

  return { dehydratedState: dehydrate(queryClient) };
}
