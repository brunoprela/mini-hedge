import type { NextRequest } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/**
 * Streaming BFF proxy — forwards SSE from the backend to the browser.
 *
 * The browser connects to `/api/stream?fundSlug=alpha` (same-origin).
 * The middleware already validates the session and injects the access
 * token via `x-auth-token` header, so we don't need to call auth() here.
 */
export async function GET(req: NextRequest) {
  const token = req.headers.get("x-auth-token");
  if (!token) {
    return new Response(JSON.stringify({ detail: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const fundSlug = req.nextUrl.searchParams.get("fundSlug");
  const url = new URL("/api/v1/stream/events", API_URL);
  url.searchParams.set("token", token);
  if (fundSlug) {
    url.searchParams.set("fund_slug", fundSlug);
  }

  const upstream = await fetch(url.toString(), {
    headers: { Accept: "text/event-stream" },
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(JSON.stringify({ detail: "Upstream stream unavailable" }), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
