import createClient from "openapi-fetch";
import type { paths } from "@mini-hedge/api-types";

/**
 * Rewrite OpenAPI-spec paths (`/api/v1/...`) to hit the Next.js BFF proxy at
 * `/api/proxy/...`. The proxy handler re-prepends `/api/v1/` when forwarding
 * to FastAPI, so we strip that prefix client-side.
 *
 * Also handles 401 → redirect to `/login`, matching `clientFetch`.
 */
async function bffFetch(input: Request): Promise<Response> {
  const url = new URL(input.url);
  const rewritten = url.pathname.startsWith("/api/v1/")
    ? `/api/proxy/${url.pathname.slice("/api/v1/".length)}${url.search}`
    : `${url.pathname}${url.search}`;

  const response = await fetch(rewritten, input);

  if (response.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
  }

  return response;
}

/**
 * Typed BFF client. All calls are routed through the same-origin `/api/proxy`
 * route, which injects the auth bearer token server-side.
 *
 * Auth headers are NOT injected here — the Next.js BFF route does that.
 * Feature-level headers (X-Fund-Slug, X-Customer-Id) can be passed via the
 * `headers` option on each call.
 */
export const api = createClient<paths>({
  baseUrl: "",
  fetch: bffFetch,
});

/** Convenience helper for callers that need to pass the fund slug header. */
export function fundHeaders(fundSlug: string): Record<string, string> {
  return { "X-Fund-Slug": fundSlug };
}

/** Convenience helper for callers that need to pass the customer id header. */
export function customerHeaders(customerId: string): Record<string, string> {
  return { "X-Customer-Id": customerId };
}
