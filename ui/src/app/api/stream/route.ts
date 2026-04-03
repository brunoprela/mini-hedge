import type { NextRequest } from "next/server";
import { auth } from "@/shared/lib/auth";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/**
 * Streaming BFF proxy — forwards SSE from the backend to the browser.
 *
 * The browser connects to `/api/stream?fundSlug=alpha` (same-origin).
 * This route validates the NextAuth session, extracts the JWT, and
 * proxies to the backend SSE endpoint with the token as a query param
 * (EventSource doesn't support custom headers).
 */
export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.accessToken) {
    return new Response(JSON.stringify({ detail: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const fundSlug = req.nextUrl.searchParams.get("fundSlug");
  const url = new URL("/api/v1/stream/events", API_URL);
  url.searchParams.set("token", session.accessToken);
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
