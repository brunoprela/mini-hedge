import createClient from "openapi-fetch";
import type { paths } from "@mini-hedge/api-types";

/**
 * Rewrite OpenAPI-spec paths (`/api/v1/...`) to hit the Next.js BFF proxy at
 * `/api/proxy/...`. The proxy handler re-prepends `/api/v1/` when forwarding
 * to FastAPI, so we strip that prefix client-side.
 */
async function bffFetch(input: Request): Promise<Response> {
  const url = new URL(input.url);
  const rewritten = url.pathname.startsWith("/api/v1/")
    ? `/api/proxy/${url.pathname.slice("/api/v1/".length)}${url.search}`
    : `${url.pathname}${url.search}`;

  return fetch(rewritten, input);
}

/**
 * Typed BFF client. All calls are routed through the same-origin `/api/proxy`
 * route, which injects the auth bearer token server-side.
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
