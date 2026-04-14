import { auth } from "@/shared/lib/auth";
import { NextResponse, type NextRequest } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function proxyRequest(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const session = await auth();
  if (!session || !(session as any).accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  if ((session as any).error === "RefreshTokenError") {
    return NextResponse.json({ detail: "Session expired" }, { status: 401 });
  }

  const { path } = await params;
  const target = `${API_URL}/api/v1/${path.join("/")}`;
  const url = new URL(target);
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));

  const headers: Record<string, string> = {
    Authorization: `Bearer ${(session as any).accessToken}`,
  };
  // Forward fund context from query params or request headers
  const fundSlug = req.nextUrl.searchParams.get("fund_slug") || req.headers.get("x-fund-slug");
  if (fundSlug) headers["X-Fund-Slug"] = fundSlug;
  const contentType = req.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.text();

  try {
    const res = await fetch(url.toString(), { method: req.method, headers, body });
    const data = await res.text();

    return new NextResponse(data, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (error) {
    console.error(`[proxy] ${req.method} ${url.pathname} failed:`, error);
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 502 },
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
export const PATCH = proxyRequest;
