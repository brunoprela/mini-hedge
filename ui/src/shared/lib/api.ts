/**
 * Legacy untyped BFF fetch helper.
 *
 * Prefer the typed client at `@/shared/lib/api-client` for all new code.
 * This helper is retained only for:
 *   - routes not yet declared in the OpenAPI spec (e.g. `/portfolios/aggregate`)
 *   - routes the backend exposes but the spec omits (e.g. `DELETE /compliance/rules/{id}`)
 *   - dead routes referenced by legacy UI that we haven't cleaned up yet
 *
 * The server-side `serverFetch` helper has been retired — server components now
 * use `openapi-fetch` via `@/shared/lib/prefetch` or a local client.
 */

/** Client-side fetch — calls BFF proxy (same-origin). */
export async function clientFetch<T>(
  path: string,
  options?: { fundSlug?: string; customerId?: string; method?: string; body?: unknown },
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options?.fundSlug) {
    headers["X-Fund-Slug"] = options.fundSlug;
  }
  if (options?.customerId) {
    headers["X-Customer-Id"] = options.customerId;
  }

  const response = await fetch(`/api/proxy${path}`, {
    method: options?.method ?? "GET",
    headers,
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Session expired");
    }
    const detail = await response.text();
    throw new Error(`API error ${response.status}: ${detail}`);
  }

  return response.json();
}
